"""Local seconds/gain predictors and train-fitted mask-aware preprocessing."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import pickle
import json
from pathlib import Path
import numpy as np
from ra.types import FeatureBatch, FeatureSchema, NodeKey


@dataclass(frozen=True)
class PredictionBatch:
    gain: np.ndarray
    body_seconds: np.ndarray
    body_q90: np.ndarray | None = None

    def validate(self, rows):
        for value in (self.gain, self.body_seconds, self.body_q90):
            if value is not None and (not isinstance(value, np.ndarray) or value.shape != (rows,)
                                      or not np.isfinite(value).all()):
                raise ValueError('invalid/nonfinite prediction batch')


def original_weights(originals):
    counts = Counter(originals)
    if not counts:
        raise ValueError('nonempty original identities required')
    return np.asarray([len(originals) / (len(counts) * counts[g]) for g in originals], dtype=np.float64)


@dataclass
class MaskPreprocessor:
    medians: np.ndarray
    centers: np.ndarray
    scales: np.ndarray

    local_width: int | None = None

    @staticmethod
    def _matrix(matrix, local_width=None):
        if (not isinstance(matrix, np.ndarray) or matrix.dtype != np.float64 or matrix.ndim != 2
                or (matrix.shape[1] if local_width is None else local_width) % 6 or not np.isfinite(matrix).all()):
            raise ValueError('finite float64 local feature matrix required')
        width = matrix.shape[1] if local_width is None else local_width
        if not 0 < width <= matrix.shape[1]: raise ValueError("invalid local prefix width")
        masks = matrix[:, :width].reshape(len(matrix), -1, 6)[:, :, 1:]
        if not np.isin(masks, [0., 1.]).all():
            raise ValueError('binary feature masks required')
        return matrix.copy()

    @classmethod
    def fit(cls, matrix, schema: FeatureSchema):
        width = next((i for i, name in enumerate(schema.names) if name.startswith("pool_")), len(schema.names))
        x = cls._matrix(matrix, width)
        if len(x) == 0 or x.shape[1] != len(schema.names):
            raise ValueError('nonempty schema-aligned training matrix required')
        medians = np.zeros(x.shape[1])
        for j in range(0, width, 6):
            missing = np.any(x[:, j+1:j+5] != 0, axis=1)
            medians[j] = np.median(x[~missing, j]) if (~missing).any() else 0.
            x[missing, j] = medians[j]
        centers = np.zeros(x.shape[1]); scales = np.ones(x.shape[1])
        columns = list(range(0, width, 6)) + list(range(width, x.shape[1]))
        centers[columns] = x[:, columns].mean(axis=0)
        scales[columns] = x[:, columns].std(axis=0)
        scales[scales == 0] = 1.
        return cls(medians, centers, scales, None if width == x.shape[1] else width)

    def transform(self, matrix):
        x = self._matrix(matrix, self.local_width)
        width = x.shape[1] if self.local_width is None else self.local_width
        if x.shape[1] != len(self.medians):
            raise ValueError('preprocessing dimension mismatch')
        for j in range(0, width, 6):
            missing = np.any(x[:, j+1:j+5] != 0, axis=1)
            x[missing, j] = self.medians[j]
        return (x - self.centers) / self.scales


@dataclass
class ModelBundle:
    schema_hash: str
    supported_lengths: tuple[int, ...]
    preprocessing: MaskPreprocessor
    gain_model: object
    body_model: object
    quantile_model: object | None
    counts: dict
    metadata: dict

    def predict(self, batch: FeatureBatch) -> PredictionBatch:
        if batch.schema_hash != self.schema_hash:
            raise ValueError('model/feature schema mismatch')
        if (len(batch.action_rows) != len(batch.matrix) or len(set(batch.action_rows)) != len(batch.action_rows)
                or any(type(key) is not NodeKey or type(key.epoch) is not int or type(key.number) is not int
                       or type(n) is not int or n not in self.supported_lengths for key, n in batch.action_rows)):
            raise ValueError('model action alignment/support mismatch')
        x = self.preprocessing.transform(batch.matrix)
        prediction = PredictionBatch(self.gain_model.predict(x), self.body_model.predict(x),
                                     None if self.quantile_model is None else self.quantile_model.predict(x))
        prediction.validate(len(x))
        return prediction

    def save(self, path):
        with Path(path).open('xb') as stream:
            pickle.dump(self, stream, protocol=5)

    def export(self, path):
        import sklearn
        if sklearn.__version__ != '1.9.1':
            raise ValueError('export requires parity-validated sklearn1.9.1 schema')
        def estimator(model):
            if model is None: return None
            if hasattr(model, 'coef_'):
                return {'kind':'linear','coefficients':model.coef_.tolist(),'intercept':float(model.intercept_)}
            trees=[]
            for stage in model._predictors:
                if len(stage)!=1: raise ValueError('only scalar numerical regressors supported')
                nodes=stage[0].nodes
                if nodes.dtype.names != ('value','count','feature_idx','num_threshold','missing_go_to_left','left',
                                         'right','gain','depth','is_leaf','bin_threshold','is_categorical','bitset_idx'):
                    raise ValueError('incompatible sklearn tree schema')
                if nodes['is_categorical'].any(): raise ValueError('categorical export unsupported')
                trees.append({name:nodes[name].tolist() for name in
                              ('value','feature_idx','num_threshold','left','right','is_leaf')})
            return {'kind':'histogram','baseline':float(model._baseline_prediction[0,0]),'trees':trees}
        raw={'version':1,'estimator_library':'scikit-learn1.9.1','tree_schema':'numeric-threshold-v1','schema_hash':self.schema_hash,'supported_lengths':self.supported_lengths,
             'preprocessing':{k:getattr(self.preprocessing,k).tolist() for k in ('medians','centers','scales')},
             'gain':estimator(self.gain_model),'body':estimator(self.body_model),'q90':estimator(self.quantile_model),
             'counts':self.counts,'metadata':self.metadata}
        if self.preprocessing.local_width is not None:
            raw['preprocessing']['local_width'] = self.preprocessing.local_width
        with Path(path).open('x') as stream: json.dump(raw,stream,allow_nan=False,separators=(',',':'))

    @classmethod
    def load(cls, path):
        if Path(path).suffix == '.json':
            from ra.worker import strict_json
            raw=strict_json(Path(path).read_text())
            if (raw['version']!=1 or raw.get('estimator_library')!='scikit-learn1.9.1'
                    or raw.get('tree_schema')!='numeric-threshold-v1'):
                raise ValueError('unsupported numeric model/library schema')
            prep=MaskPreprocessor(**{k:(v if k == "local_width" else np.asarray(v,dtype=float)) for k,v in raw['preprocessing'].items()})
            return cls(raw['schema_hash'],tuple(raw['supported_lengths']),prep,
                NumericRegressor(raw['gain']),NumericRegressor(raw['body']),
                None if raw['q90'] is None else NumericRegressor(raw['q90']),raw['counts'],raw['metadata'])
        # Assets are local trusted training outputs; caller verifies the exact hash first.
        with Path(path).open('rb') as stream:
            result = pickle.load(stream)
        if type(result) is not cls:
            raise ValueError('invalid model bundle')
        return result


def fit_bundle(batch, schema, gain, body_seconds, originals, body_eligible, *, kind, seed,
               parameters=None, quantile=False, supported_lengths=None, gain_eligible=None):
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import HistGradientBoostingRegressor
    from threadpoolctl import threadpool_limits
    parameters = dict(parameters or {})
    gain, body = np.asarray(gain, dtype=float), np.asarray(body_seconds, dtype=float)
    eligible = np.asarray(body_eligible, dtype=bool)
    n = len(batch.matrix)
    gain_ok = np.ones(n,dtype=bool) if gain_eligible is None else np.asarray(gain_eligible,dtype=bool)
    if (batch.schema_hash != schema.hash or any(a.shape != (n,) for a in (gain, body, eligible, gain_ok))
            or len(originals) != n or not np.isfinite(gain).all() or not np.isfinite(body).all()
            or (body < 0).any() or not eligible.any() or not gain_ok.any()):
        raise ValueError('invalid aligned training targets/schema')
    prep = MaskPreprocessor.fit(batch.matrix, schema)
    x = prep.transform(batch.matrix)
    def estimator(q=None):
        if kind == 'ridge':
            if q is not None: raise ValueError('ridge quantile unsupported')
            return Ridge(**parameters)
        if kind == 'histogram':
            return HistGradientBoostingRegressor(loss='squared_error' if q is None else 'quantile',
                quantile=q, random_state=seed, early_stopping=False, **parameters)
        raise ValueError('unsupported estimator')
    weights = original_weights([g for g, ok in zip(originals, gain_ok) if ok])
    body_weights = original_weights([g for g, ok in zip(originals, eligible) if ok])
    with threadpool_limits(limits=1):
        gm = estimator().fit(x[gain_ok], gain[gain_ok], sample_weight=weights)
        bm = estimator().fit(x[eligible], body[eligible], sample_weight=body_weights)
        qm = estimator(.9).fit(x[eligible], body[eligible], sample_weight=body_weights) if quantile else None
    observed = sorted({length for _, length in batch.action_rows})
    support = tuple(observed if supported_lengths is None else supported_lengths)
    if not support or len(set(support)) != len(support) or any(type(n) is not int or n <= 0 for n in support) or not set(observed) <= set(support):
        raise ValueError('invalid declared action support')
    return ModelBundle(schema.hash, support, prep, gm, bm, qm,
        {'gain_rows': int(gain_ok.sum()), 'zero_gains': int((gain[gain_ok] == 0).sum()), 'body_rows': int(eligible.sum()),
         'excluded_body_rows': int((~eligible).sum()), 'originals': len(set(originals))},
        {'kind': kind, 'seed': seed, 'parameters': parameters, 'quantile': quantile, 'observed_lengths': observed})


class NumericRegressor:
    """Generic finite numeric regression export; no sklearn import at deployment."""
    def __init__(self, raw):
        self.kind=raw['kind']
        if self.kind=='linear':
            self.coefficients=np.asarray(raw['coefficients'],dtype=float)
            self.intercept=float(raw['intercept'])
            if self.coefficients.ndim!=1 or not np.isfinite(self.coefficients).all() or not np.isfinite(self.intercept):
                raise ValueError('invalid linear export')
        elif self.kind=='histogram':
            self.baseline=float(raw['baseline'])
            if not np.isfinite(self.baseline): raise ValueError('invalid tree baseline')
            self.trees=[{k:np.asarray(v,dtype=float if k in ('value','num_threshold') else np.intp)
                         for k,v in tree.items()} for tree in raw['trees']]
            for tree in self.trees:
                if set(tree)!={'value','feature_idx','num_threshold','left','right','is_leaf'}:
                    raise ValueError('invalid tree fields')
                n=len(tree['value'])
                if not n or any(v.shape!=(n,) or not np.isfinite(v).all() for v in tree.values()):
                    raise ValueError('invalid tree arrays')
                if (not np.isin(tree['is_leaf'],[0,1]).all() or (tree['feature_idx']<0).any()
                        or any((tree[k]<0).any() or (tree[k]>=n).any() for k in ('left','right'))):
                    raise ValueError('invalid tree indices')
                for i in range(n):
                    if not tree['is_leaf'][i] and (tree['left'][i]<=i or tree['right'][i]<=i):
                        raise ValueError('invalid tree topology')
        else: raise ValueError('unsupported numerical regressor')

    def predict(self,x):
        if self.kind=='linear': return x@self.coefficients+self.intercept
        result=np.full(len(x),self.baseline)
        rows=np.arange(len(x))
        for tree in self.trees:
            index=np.zeros(len(x),dtype=np.intp)
            for _ in range(len(tree['value'])):
                leaf=tree['is_leaf'][index].astype(bool)
                if leaf.all(): break
                go_left=x[rows,tree['feature_idx'][index]]<=tree['num_threshold'][index]
                index=np.where(leaf,index,np.where(go_left,tree['left'][index],tree['right'][index]))
            else: raise ValueError('invalid/cyclic exported tree')
            result+=tree['value'][index]
        return result

# Third-party notices

The project licenses apply to original project material. They do not relicense
dependencies, cited research, external repositories or embedded fonts.

## Fonts in the published figures

The four PDFs in `results/confirmatory/` and `results/handoff/` embed DejaVu Sans.
Its Bitstream and Arev copyright and permission notices are retained unchanged in
[licenses/third-party/LICENSE_DEJAVU](licenses/third-party/LICENSE_DEJAVU).
That notice was copied from the Matplotlib 3.10.7 plotting environment used for
these figures; SHA-256:
`d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e`.

CC BY 4.0 covers the original plot presentation, with the embedded font software
remaining under its own terms. No font file or installed plotting environment is
bundled here. Figure bytes are unchanged from the retained research results.

## Installed dependencies

The implementation depends on PySCIPOpt, NumPy, SciPy, scikit-learn, psutil and
threadpoolctl. PySCIPOpt's Python wrapper is MIT licensed; the linked SCIP and
SoPlex libraries are separate components. The measured build links SCIP 10.0.2
and SoPlex 8.0.2, whose project licenses are Apache-2.0. The wrapper's MIT notice
does not describe every component of a solver wheel.

NumPy and SciPy have project and bundled-component notices. scikit-learn, psutil,
joblib, cloudpickle and threadpoolctl use BSD terms; pytest, pluggy and iniconfig
use MIT terms. The installed packages' notices govern their distributions.
[requirements.lock](requirements.lock) pins the measured macOS ARM64 runtime and
test wheels; it is not a binary redistribution or complete native-component
clearance inventory.

Plotting uses a separate environment recorded in
[requirements/analysis-plot.in](requirements/analysis-plot.in) and
[requirements/analysis-plot.lock](requirements/analysis-plot.lock). Matplotlib and
its dependencies retain their own notices. The installed runtime and plotting
environments, wheel caches and native libraries remain external to this source
release. Redistributing them would require a separate component-specific review,
including solver and linked runtime notices.

## Literature and external benchmarks

The [baseline cards](baselines/cards/) and
[source-access audit](docs/superpowers/evidence/task14/baseline-source-audit.md)
reference Labassi et al., Mattick–Mutschler, TRGNN, DeepBound and TreeCL. Their
implementations, checkpoints and teacher assets are not included. Unresolved
reuse or reproduction gates remain unresolved; the project license grants no
rights to those authors' software or papers.

MIPLIB transfer was not executed, and no MIPLIB instance archive is included.
The core experiment uses project-generated weighted-set-cover instances.
Linked papers, websites and datasets retain their original rights. Citations
identify prior work; they do not grant redistribution permission.

# NASA IMS Bearing Dataset

Obtain the IMS bearing data from the [NASA catalog](https://data.nasa.gov/dataset/ims-bearings).
NASA's current catalog marks it public and links government-work terms, while
also attributing the data to the University of Cincinnati IMS center. Recheck
those terms at staging; this project does not redistribute source files.

Stage Set 2 only after verifying its bundled README, channel layout, and stated
20 kHz sampling and 20,480 samples per recording against the bundled README.
The 20 kHz value is also reported in [NASA NTRS 20205001055](https://ntrs.nasa.gov/citations/20205001055).
The apparent duration/sample-count mismatch must remain documented, not guessed away.

```powershell
./infra/scripts/stage-dataset.ps1 -Dataset ims -SourcePath C:\secure\ims-set2 -StorageAccount <name>
```

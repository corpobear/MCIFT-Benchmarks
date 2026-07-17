# Dataset staging

Datasets are never downloaded by automation or committed to Git. An operator must
obtain each dataset from its authoritative source, review the current terms, and
stage it privately with Microsoft Entra ID. Redistribution rights can change;
the project makes no blanket permission claim. At preparation time, NASA catalog
metadata marked IMS public/government-work while attributing IMS/University of
Cincinnati, and Exathlon's official README specified CC BY-NC-SA 4.0 for data.

The staging scripts calculate per-file SHA-256 values, write a manifest, enforce
the `datasets/<dataset>/` destination prefix, and use resumable `az storage blob
upload-batch --auth-mode login`. Generated manifests are local artifacts until
reviewed and are ignored by Git.

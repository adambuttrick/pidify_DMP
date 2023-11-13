## Overview
Basic example of processing PDFs outputted by DMPTool, extracting and "PIDifying" their information by searching various APIs (ORCID, ROR, CrossRef).


## Installation
```
pip install -r requirements.txt
```

## Usage
```
python pidify.py -i [input_pdf]
```
- `[input_pdf]`: Path to the input PDF file.

## Output
The script outputs a JSON string that contains:
- Input details (DMP ID, affiliation, funder name, funding opportunity number).
- Matched data (ORCID, ROR IDs, CrossRef award works, etc.).
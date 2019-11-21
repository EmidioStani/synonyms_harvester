# synonyms_harvester
A python script to enrich a skos list with synonyms taken from different sources

The script uses the following data sources:

1) Wiktionary:
   - downloaded from dbnary (http://kaiko.getalp.org/about-dbnary/download/ the core in English)
   - uploaded on GraphDB (under the user folder graphdb-import) with graph name "wiktionary"
   - the data is filtered with the script getSynonymsWiktionary.py which generates a file with name syn_wiktionary.ttl (already present in this repository)
   - as the syn_wiktionary.ttl file is relatively small it is parsed directly

2) Wordnet:
  - downloaded from wordnet-rdf (https://wordnet-rdf.princeton.edu/about)
   - uploaded on GraphDB (under the user folder graphdb-import) with graph name "wordnet"
   - the data is filtered with the script getSynonymsWordnet.py which generates a file with name syn_wordnet.ttl (already present in this repository)
   - the file has been uploaded on the graph name "wordnet-synonyms"

3) Unesco:
  - downloaded from vocabularies.unesco.org (http://vocabularies.unesco.org/exports/thesaurus/latest/)
   - uploaded on GraphDB (under the user folder graphdb-import) with graph name "unesco"

If no value has been found in 1),2) or 3) then search in:

4) Datamuse API (max 100.000 requests per day with no key):
   - connecting to https://www.datamuse.com/api/ via https://github.com/gmarmstrong/python-datamuse

If no value has been found in Datamuse API then search in:

5) Altervista API (max 5.000 requests per day with key to be passed to the script see below):
   - connecting to http://thesaurus.altervista.org/

Usage:
```
getSynonyms.py [-h] [-k KEY] [-w WIK_FILE] [-i INPUT_FILE] [-o OUTPUT_FILE]

optional arguments:
  -h, --help "show this help message and exit"

  -k KEY, --apikey KEY "Api key file for Altervista"

  -w WIK_FILE, --wiktionaryfile WIK_FILE "syn file for wikitionary"

  -i INPUT_FILE, --input INPUT_FILE "input file in RDF/XML"

  -o OUTPUT_FILE, --output OUTPUT_FILE  "output file in Turtle"

```

Example:
```
python getSynonyms.py -k 1234567890 # replace it with your own key
```
would generate by default the file "output.ttl" containing the synonyms as SKOS alternative labels.
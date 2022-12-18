from rdflib import Graph
from SPARQLWrapper import TURTLE, SPARQLWrapper

sparql = SPARQLWrapper("http://localhost:7200/repositories/wiktionary")
sparql.setQuery("""
    PREFIX dbnary: <http://kaiko.getalp.org/dbnary#>
    PREFIX ontolex: <http://www.w3.org/ns/lemon/ontolex#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    CONSTRUCT {
      ?term rdf:type skos:Concept .
      ?term skos:prefLabel ?termlabel .
      ?term skos:altLabel ?synlabel .
    }
    WHERE {
      ?term rdf:type ontolex:LexicalEntry .
      ?term dbnary:partOfSpeech "Noun" .
      ?term dbnary:synonym ?syn .
      BIND(strlang(strafter(str(?syn),"eng/"),"en") as  ?synlabel) .
      BIND(strlang(strbefore(strafter(str(?term),"eng/"), "__Noun"),"en") as  ?termlabel) .
    }
""")

sparql.setReturnFormat(TURTLE)
results = sparql.query().convert()

g = Graph()
g.parse(data=results, format="turtle")
g.serialize(destination='syn_wiktionary_2.ttl', format='turtle')

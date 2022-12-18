from rdflib import Graph
from SPARQLWrapper import TURTLE, SPARQLWrapper

sparql = SPARQLWrapper("http://localhost:7200/repositories/eurovoc")
sparql.setQuery("""
  PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
  PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
  PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>
  CONSTRUCT {
      ?s rdf:type skos:Concept.
      ?s skos:prefLabel ?prefLabel .
      ?s skos:altLabel ?alt .
  }
  where { 
    ?s skos:inScheme ?o .
      ?o skos:prefLabel ?Scheme .
      FILTER (lang(?Scheme) = 'en') .
      FILTER (?Scheme NOT IN ("7626 non-governmental organisations"@en, "7621 world organisations"@en, "7616 extra-European organisations"@en, "7611 European organisations"@en, "7211 regions of EU Member States"@en, "7606 United Nations"@en, "7241 overseas countries and territories"@en, "7236 political geography"@en, "7231 economic geography"@en, "7226 Asia and Oceania"@en, "7221 Africa"@en, "7216 America"@en, "7206 Europe"@en, "EuroVoc"@en))
      ?s rdf:type skos:Concept.
      ?s skos:prefLabel ?prefLabel .
      ?s skosxl:altLabel ?altLabel .
      ?altLabel skosxl:literalForm  ?alt .
      FILTER (lang(?prefLabel) = 'en') .
      FILTER (lang(?alt) = 'en') .
  }
""")

sparql.setReturnFormat(TURTLE)
results = sparql.query().convert()

g = Graph()
g.parse(data=results, format="turtle")
g.serialize(destination='syn_eurovoc.ttl', format='turtle')

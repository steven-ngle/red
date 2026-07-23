# red

ein kleines POC, was ein Agentic RAG mit LangGraph emulieren soll. 

Der stack war dabei:

- langGraph für den graphen/loop
- deepSeek v4-flash als llm (ist sehr günstig)
- tavily für die websuche
- mem0 + qdrant lokal als langzeitgedächtnis
- rich für die cli ausgabe

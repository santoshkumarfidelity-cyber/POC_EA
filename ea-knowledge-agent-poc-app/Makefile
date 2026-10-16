.PHONY: run test reset-demo check

run:
	PYTHONPATH=src python3 -m ea_knowledge_agent --host 127.0.0.1 --port 8765 --db data/poc.db

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

reset-demo:
	rm -f data/poc.db

check:
	PYTHONPATH=src python3 -m compileall -q src tests
	PYTHONPATH=src python3 -m unittest discover -s tests

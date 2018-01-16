# Ritual

Ritual is an experimental parser generator / compiler.  Instead of trying to immediately create a self-hosting language, Ritual is structured as a series of increasingly complex "phases", each supporting a wider range of features. Self-hosting requires a degree of stability that is incompatible with the early stages of language creation. "Phased" construction allows earlier phases to stay stable, at the cost of some redundant work.

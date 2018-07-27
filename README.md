# Ritual

Ritual is an experimental parser generator / compiler.  Instead of trying to immediately create a self-hosting language, Ritual is structured as a series of increasingly complex "phases", each supporting a wider range of features. Self-hosting requires a degree of stability that is incompatible with the early stages of language creation. "Phased" construction allows earlier phases to stay stable, at the cost of some redundant work.

## Getting started

Setup git:

    ./tools/install_hooks.sh

Development:

    ./tools/workflow.sh

## Scale

Scale is a language (currently implemented using Ritual) for creating compilers.  It will eventually self host.

### Scale Design Philosophy

Pattern matching and data structure transformation is fundemental.

Parser is the primary way to process strings.  Strings are UTF8 and not indexable.

Compile to a low-level target.

GC - total latency matters, not realtime behavior.

Deterministic, defined behavior.

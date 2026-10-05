# Quiz authoring

`raw.json` holds the question text extracted (`parse.py`) from the FAA's public-domain
sample knowledge-test PDFs. The FAA publishes no answer key, so `answers_<test>.py`
records each answer, an original explanation and its citation (eCFR, PHAK, AIM, or the
FAA testing-supplement figure), written and checked by hand. `author.py` merges them
into `../<test>.json`, which `tools/site_quiz.py` renders. Questions with no single
defensible answer are left out on purpose (see the `skip` notes in the answer files).

# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Content checks for posts and categories.

Three levels, cheapest first:

1. Local (scorer.py, topic.py): a violation score and a topic-mismatch
   score in percent, computed without any outside call. Runs before a post
   or category is published (and, once payments exist, before one is
   charged).
2. AI model (ai.py): the same question put to a model. Prepared - request,
   prompt, response contract - but only a mock is connected so far.
3. Manual: an administrator blocks a post with a reason (admin_router.py).

assess.py ties the first two together into one Assessment.
"""

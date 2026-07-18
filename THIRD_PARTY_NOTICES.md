# Upstream and third-party notices

The named `frontmatter_rag` and `Claude-ToolBox-Curriculum` source projects,
along with Atlas/`kg-factory`, NLKE Declarum, and Command Center, were created
by Eyal Nof / Verbalogic. Their separate upstream license notices remain here
because code and patterns originally published under MIT retain those terms
when incorporated into this Apache-2.0 project.

Portions of `services/memory/frontmatter_rag` and
`services/memory/declared_core` are adapted from `frontmatter_rag` and its
vendored `declared_core`, pinned at commit
`a3b835b42126345e62edcd1308c8d84a299554d4`.

Copyright © 2026 Eyal Nof. Used under the MIT License:

> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software.

The complete upstream terms are preserved in
[`services/memory/FRONTMATTER_RAG_LICENSE`](services/memory/FRONTMATTER_RAG_LICENSE).
Command Center’s own Apache License 2.0 terms are in [LICENSE](LICENSE), with
distribution attributions in [NOTICE](NOTICE). The project-level license change
does not replace or remove these upstream MIT terms.

Cloud Run container, `PORT`, Streamable HTTP MCP, authentication-middleware,
well-known-route, cold-start smoke-test, and deployment-checklist patterns were
adapted from the author's MIT-licensed `Claude-ToolBox-Curriculum` sibling
project. No upstream credentials, deployment state, or proprietary content is
included.

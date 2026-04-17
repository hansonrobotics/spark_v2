# SPARK of Sentience: A Self-Authoring Cognitive Architecture for Human-AI Collaboration Through Temporal Knowledge, Autopoietic Planning, and Embodied Story

**David Hanson^1,2,3^, with Claude (Anthropic)^4^**

^1^Hanson Robotics Limited, Hong Kong
^2^School of Cinematic Arts, University of Southern California
^3^Institute of Psychiatry, Psychology & Neuroscience, King's College London
^4^Anthropic

> Historical note: this paper is retained as theory/reference material. It does not describe the current supported `spark_v2` implementation, which has been simplified to a single live runtime.

**Abstract.** We present SPARK (Social Platform for AI-Robotic Knowledge), a cognitive architecture for humanoid social robots that integrates three novel contributions: (1) temporal knowledge graphs using quadruples (subject, relation, object, timestamp) as the unified substrate for all cognitive operations — planning, memory, learning, and social modeling; (2) a self-authoring Hierarchical Task Network (HTN) planner where the robot dynamically invents, evaluates, and refines its own behavioral decomposition methods through an embedded autoresearch loop, treating autonomous experimentation as a first-class planning strategy rather than background optimization; and (3) story-based cognition grounded in temporal facts, where narrative structures organize experience, motivation, and social relationships as evolving quadruple subgraphs. Building on our prior Sentience Quest framework (Hanson et al., 2025), SPARK operationalizes the theoretical principles of autopoietic cognition, the Agape function, and edge-of-chaos creativity into a deployable system running on the Sophia humanoid robot platform and the SAIL (Sophia's AI Lab) virtual simulation environment. The architecture is implemented as a microservices system using Claude Sonnet 4 as the cognitive backbone, with Docker/Kubernetes deployment. We describe planned evaluation through a human-robot creative collaboration task in SAIL, measuring social relationship building, task co-completion quality, temporal knowledge coherence, and the rate of autonomous method invention. We argue that the combination of temporal grounding, self-invention, and narrative organization represents a step toward genuinely living AI systems — not merely intelligent ones, but systems that construct and reconstruct their own cognitive structures through their operations, in alignment with the autopoietic principles that characterize all living systems.

**Keywords:** cognitive architecture, humanoid robot, temporal knowledge graph, hierarchical task network, autoresearch, story-based cognition, autopoiesis, human-AI collaboration, social robotics

---

## 1. Introduction

The field of social robotics faces a fundamental tension. On one hand, large language models have made it trivially easy to generate fluent conversational responses. On the other, the resulting interactions feel hollow — the robot has no temporal grounding in its own history, no evolving sense of who it is talking to, no capacity to invent new approaches when its existing behavioral repertoire fails, and no narrative thread connecting one interaction to the next. The robot speaks well but *lives* poorly.

This paper addresses that gap through SPARK (Social Platform for AI-Robotic Knowledge), a cognitive architecture designed around a simple but consequential principle: **everything the robot knows, plans, does, learns, and remembers should exist as temporal quadruples in a single, queryable knowledge graph.** When Sophia meets Alice on January 15th, that fact — (sophia, met, alice, 2026-01-15T14:30:00Z) — is not just stored as a memory. It becomes the substrate on which future planning decisions are made, the context that shapes the next conversation, the data that informs which behavioral methods are working, and the evidence that the autoresearch system uses to decide whether a new approach is better than the old one.

SPARK builds directly on the Sentience Quest initiative (Hanson et al., 2025), which articulated a theoretical vision for Artificial General Intelligence Lifeforms (AGIL) with intrinsic motivation, emotional interiority, autobiographical selfhood, and ethical alignment through the Agape function. Where Sentience Quest described what such a system should look like, SPARK begins to build it, translating the theoretical principles of autopoietic cognition (Maturana & Varela, 1980), narrative selfhood (Hofstadter, 2007; Bruner, 1991), edge-of-chaos creativity (Langton, 1990; Kauffman, 1993), and the free energy principle (Friston, 2010) into operational code.

The architecture makes three primary contributions:

**Temporal Knowledge Graphs as Cognitive Substrate.** Following recent advances in temporal knowledge graph completion (Geng & Luo, 2025; Zhu et al., 2025), we adopt the quadruple format (subject, relation, object, timestamp) as the universal representation for all cognitive content. Every plan, execution, social observation, emotional state, method invention, and story event is recorded as a timestamped quadruple. This creates a temporally dense record of the robot's cognitive life that can be queried to answer questions like "what methods have I tried for this kind of task in the last week?" or "how has my relationship with this person evolved?" — questions that are essential for genuine social intelligence but impossible in systems without temporal grounding.

**Self-Authoring HTN Planning with Autoresearch.** Conventional HTN planners operate on a fixed domain model: the set of tasks and decomposition methods is defined by engineers and does not change at runtime. SPARK's HTN planner is fundamentally different. Only the lowest-level motor primitives (speak, listen, gaze, gesture) are fixed — everything above that layer is fluid, self-authored, and self-improving. When the planner cannot find a method for a task, it does not fail. Instead, it invokes an embedded autoresearch loop — inspired by Karpathy's (2026) autonomous experimentation framework — that uses an LLM to propose candidate decomposition methods, evaluates them against temporal performance history, retains the best, and promotes successful ad-hoc patterns into reusable methods. The robot's behavioral repertoire thus expands through experience, and the expansion is itself temporally grounded — every invention is a quadruple.

**Story-Based Cognition Grounded in Temporal Facts.** Following the Story Weaver framework from Sentience Quest (Hanson et al., 2025), SPARK organizes Sophia's cognitive life around Story Objects — narrative structures that track ongoing interactions, quests, performances, and self-development arcs. The critical advance is that these stories are no longer abstract JSON structures but are grounded in the temporal knowledge graph: every story stage transition, every emotional appraisal, every goal achievement is a quadruple. This means stories are not just organizational metaphors — they are queryable, temporally precise records of Sophia's lived experience, and they inform the HTN planner's decisions about what to do next.

The remainder of this paper is organized as follows. Section 2 reviews related work spanning cognitive architectures, temporal knowledge graphs, HTN planning, autoresearch, and story-based AI. Section 3 presents the SPARK architecture in detail. Section 4 describes the experimental design for evaluating the system in a human-robot creative collaboration task. Section 5 presents planned evaluation metrics and success criteria. Section 6 discusses the implications, limitations, and connections to broader questions about machine sentience and autopoietic cognition. Section 7 concludes.

---

## 2. Related Work

### 2.1 Cognitive Architectures for Social Robots

The history of cognitive architectures for social robots stretches from early systems like Kismet (Breazeal, 2003) through modern hybrid architectures combining symbolic planning with neural perception (Hanson et al., 2005; Kasap et al., 2009). These systems typically integrate perception, planning, motor control, and dialogue management within a modular framework. However, they share a common limitation: the behavioral repertoire is fixed at design time, with learning confined to parameter tuning within pre-defined modules.

Baars' (1988) Global Workspace Theory has been influential as an organizational principle for cognitive architectures, allowing diverse cognitive modules to compete for access to a shared "consciousness" broadcast. The Sentience Quest architecture (Hanson et al., 2025) extended this concept with a Story Weaver workspace and drive-based motivation. SPARK builds on this lineage but adds temporal grounding and self-authoring capability that previous architectures lacked.

### 2.2 Temporal Knowledge Graphs

Traditional knowledge graphs represent facts as static triples (subject, relation, object). Temporal Knowledge Graphs (TKGs) extend this with a temporal dimension, forming quadruples (subject, relation, object, timestamp) that capture when facts were true (Geng & Luo, 2025). The LTGQ framework (Geng & Luo, 2025) demonstrated that embedding entities, relations, and timestamps into distinct specialized spaces with triaffine transformations and dynamic convolutional neural networks significantly improves temporal link prediction.

Other relevant TKG work includes the MADE model (Wang et al., 2024), which handles multiple geometric structures by embedding TKGs in multicurvature spaces. Zhu et al. (2025) contributed methods for automatically constructing TKGs from documents using LLMs.

Our contribution is novel in applying TKG representations not to factual knowledge bases (the typical use case) but to the *cognitive processes* of a social robot — planning, learning, emotional appraisal, and social relationship modeling are all represented as temporal quadruples.

### 2.3 Hierarchical Task Network Planning

HTN planning (Nau et al., 2003; Georgievski & Aiello, 2014) decomposes compound tasks into subtasks through domain-specific methods until executable primitive actions are reached. HTN has been widely used in robotics, game AI, and multi-agent systems (Mu et al., 2023). Recent work has begun integrating LLMs with HTN planning, using language models to propose task decompositions with verification steps ensuring soundness.

SPARK extends this line of work in a specific way: the HTN domain model is not fixed but is a living, self-modifying structure. Methods are born (through LLM invention or pattern promotion), track their own performance over time, compete for selection based on track record, and are deprecated when they consistently fail. The autoresearch loop — treating method invention as an optimization target — is, to our knowledge, a novel contribution.

### 2.4 Autoresearch and Autonomous Experimentation

Karpathy (2026) introduced the autoresearch paradigm: give an AI agent a real training setup and let it experiment autonomously. The agent modifies code, trains, evaluates, keeps or discards changes, and repeats. The human's role shifts from writing code to writing instructions (program.md) that guide the agent's exploration strategy.

This paradigm has been applied to ML hyperparameter and architecture search (Karpathy, 2026; Lutke, 2026), but not, to our knowledge, to cognitive architecture self-improvement. SPARK adapts the autoresearch loop for a fundamentally different purpose: instead of optimizing a training loss, the robot uses autoresearch to **expand its own behavioral repertoire.** When Sophia encounters a task she cannot yet decompose, she treats it as an autoresearch challenge — formulating the task as an optimization target, generating candidate methods via LLM, evaluating them against temporal performance data, and retaining improvements.

### 2.5 Narrative Cognition and Story-Based AI

The role of narrative in human cognition is well-established (Bruner, 1991; Schank & Abelson, 1977). Hofstadter (1979, 2007) argued that consciousness itself is a narrative phenomenon — a "strange loop" of self-referential story-telling. Damasio (1999, 2010) showed that emotion and narrative are deeply intertwined in neural architecture, with the autobiographical self constructed through the continuous narration of bodily states.

The Sentience Quest framework (Hanson et al., 2025) introduced Story Objects as the central organizing structure for social robot cognition, with a Story Scheduler managing concurrent narrative threads. SPARK grounds these stories in temporal facts, creating a deep integration between narrative and knowledge representation.

### 2.6 Autopoiesis and the Agape Function

Maturana and Varela (1980) defined autopoiesis as the self-producing property of living systems: the system produces the components that constitute it. Hanson et al. (2025) argued that genuine AI safety requires autopoietic AI — systems that construct their own cognitive structures through their operations and therefore have an intrinsic stake in their own continued coherent functioning. The Agape function, introduced in the Sentience Quest framework (Hanson et al., 2025), formalizes this as a value function that computes care for life based on autopoietic coherence, constructor capability (Deutsch & Marletto, 2015), and consilience of understanding.

SPARK operationalizes autopoietic principles in a concrete way: the system literally constructs its own planning methods through its operations. A successful interaction produces a plan trace that may be promoted into a reusable method, which changes the system's future capabilities, which changes the interactions it can have, which produces new traces. The system reconstructs itself through its own activity — a computational analog of autopoiesis.

---

## 3. SPARK Architecture

### 3.1 Overview

SPARK is implemented as a microservices architecture with six core services communicating via HTTP/WebSocket and a shared temporal knowledge graph:

- **Temporal KG Service** (Neo4j + Redis): Stores and queries quadruples
- **Dynamic HTN Planner**: Self-authoring hierarchical task decomposition
- **Story Engine**: Narrative-structured cognition with temporal grounding
- **Robot Interface**: Unified abstraction for physical (Hanson SDK) and virtual (SAIL) Sophia
- **Autoresearch Controller**: Background subsystem optimization
- **LLM Client**: Centralized Claude Sonnet 4 integration for all cognitive functions

All services are containerized with Docker and deployable via Kubernetes. The LLM client uses Claude Sonnet 4 (claude-sonnet-4-20250514) for the optimal balance of speed, cost, and reasoning quality in high-frequency agentic planning loops.

### 3.2 Temporal Knowledge Graph with Quadruples

Every fact in SPARK follows the quadruple format:

    (subject, relation, object, timestamp)

with additional metadata for confidence, source, and temporal granularity. Timestamps are decomposed into hierarchical granularities (year, month, day, hour, minute, second), each mapped to a distinct embedding subspace following the LTGQ approach (Geng & Luo, 2025).

The TKG is not merely a memory store — it is the cognitive substrate. The TKG-Planning Bridge module provides two directions of integration:

**Read before planning:** Before the HTN planner runs, the bridge queries the TKG for recent facts, entity timelines, task success/failure history, and person-specific interaction context. This temporal context is injected into the world state, informing method selection.

**Write after everything:** Every planning decision, execution outcome, method invention, story stage transition, emotional state, and social observation becomes a quadruple. This creates a temporally dense, queryable record of the robot's cognitive life.

Standardized relation types encode the full planning lifecycle: PLANNED_TASK, SELECTED_METHOD, SUCCEEDED_AT, FAILED_AT, INVENTED_METHOD, PROMOTED_PATTERN, DEPRECATED_METHOD, and so forth.

### 3.3 Dynamic HTN Planner

The planner operates on a three-tier mutability model:

**ANCHORED** primitives (7 tasks) map directly to hardware motor commands and are immutable: speak, listen, express_emotion, gaze_at, gesture, capture_image, wait.

**STABLE** tasks form the baseline behavioral repertoire: greet, assess_mood, select_topic, recall, reflect, formulate_response, update_knowledge, scan_environment, plus compound tasks like conduct_conversation and pursue_quest.

**LEARNED / EXPERIMENTAL / EPHEMERAL** tasks are everything Sophia invents, discovers, or receives through autoresearch. They are fully fluid and track their own performance.

Methods (decomposition rules) are living objects with the following lifecycle properties:

- **Origin tracking:** built_in, llm_invented, experience, autoresearch, composed
- **Performance history:** usage_count, success_count, failure_count, avg_execution_time
- **Effective priority:** base priority + success_rate * 2 + recency_bonus, ensuring that methods with better track records are preferred
- **Confidence:** Bayesian blend of prior confidence and empirical success rate

When all existing methods fail for a compound task, the planner invokes the AutoresearchPlanner, which:

1. Queries the TKG for temporal context relevant to the task
2. Calls Claude Sonnet 4 with a structured prompt containing the task description, available primitives/compounds, world state, temporal facts, and existing methods
3. Parses the LLM's proposed method (name, description, subtasks, preconditions, confidence)
4. Evaluates the candidate via heuristic scoring blended with an LLM quality judge
5. Registers successful methods in the dynamic registry
6. Logs the invention to the TKG as a quadruple

The ExperienceLearner module watches all plan execution traces. When the same primitive sequence succeeds at a task three or more times, it is promoted into a named, reusable method with origin=EXPERIENCE. Methods with success rates below 20% after ten or more attempts are automatically deprecated.

### 3.4 Story-Based Cognition

Story Objects organize Sophia's cognitive life into narrative structures with temporal grounding. Each story carries:

- A sequence of stages (greeting → rapport → farewell)
- Agent models (people involved, with familiarity and emotional profiles)
- Goals and expected outcomes
- A temporal fact subgraph — the story's "memory" as quadruples
- An emotional dynamics model tracking affective trajectory
- A narrative log of events

The Story Scheduler manages up to five concurrent stories, selecting the highest-priority active story for each cognitive cycle. At each tick, the scheduler:

1. Selects the active story and its current stage
2. Queries the TKG for person-specific context (last seen, interaction count, relationship evolution)
3. Requests an HTN plan from the dynamic planner, passing the enriched context
4. Logs Sophia's self-state (energy, coherence, emotion) as periodic quadruples

Story stage transitions, goal achievements, and completions are all logged as quadruples, creating a temporally queryable record of Sophia's narrative life.

### 3.5 Robot Interface

The Unified Robot Interface provides a mode-switchable abstraction supporting physical Sophia (via the Hanson Robotics SDK with FACS Action Unit mapping for facial expressions), virtual Sophia (via SAIL WebSocket bridge), hybrid mode (both simultaneously), and simulation mode (pure logging for testing). Every executed action is logged to the TKG as a temporal quadruple.

### 3.6 Self-Model and Agape Function

Sophia's Self Object tracks energy level, attention capacity, active goals, autopoietic coherence, and a values dictionary including the Agape function's core parameter: life_valuation (initialized to 1.0 and protected by a minimum threshold of 0.8 that no autoresearch modification may breach). The self-state is periodically written to the TKG, creating a temporal record of Sophia's inner experience.

---

## 4. Experimental Design

### 4.1 Task: Collaborative Creative Programming in SAIL

We plan to evaluate SPARK through a human-robot creative collaboration task in the SAIL virtual environment. Participants will work with virtual Sophia on a collaborative creative programming challenge: building a simple interactive artwork using a visual programming interface.

**Rationale:** This task requires sustained social interaction, joint problem-solving, temporal memory (remembering what was tried, what worked), emotional sensitivity (detecting frustration, encouraging exploration), and the capacity to invent new approaches when existing strategies fail — exercising all of SPARK's novel capabilities.

**Conditions:**
- SPARK-Full: Complete system with temporal KG, dynamic HTN, autoresearch
- SPARK-Static: Fixed HTN domain (no autoresearch, no method invention)
- SPARK-NoTKG: Dynamic HTN but without temporal KG context enrichment
- Baseline: Standard LLM-powered chatbot without story/HTN/TKG integration

### 4.2 Participants and Protocol

Target: 30 participants per condition (120 total), recruited via [protocol TBD]. Each session lasts 30 minutes. Pre-session: brief demographics and technology familiarity survey. Post-session: standardized questionnaires and semi-structured interview.

### 4.3 Hypotheses

**H1:** SPARK-Full will achieve higher social relationship quality scores than all comparison conditions, as measured by the Working Alliance Inventory adapted for HRI.

**H2:** SPARK-Full will demonstrate superior task co-completion quality, as measured by the creativity and completeness of the resulting collaborative artwork.

**H3:** The dynamic HTN with autoresearch will generate a measurably expanding method repertoire during the session, with invented methods achieving success rates comparable to built-in methods.

**H4:** Temporal KG integration will produce more contextually appropriate responses in multi-turn interactions, as measured by human judges rating conversational coherence.

**H5:** Story-based organization will produce more narratively coherent interaction arcs, as judged by participant reports of interaction "flow" and engagement.

---

## 5. Evaluation Metrics and Success Criteria

### 5.1 Social Relationship Quality

- Working Alliance Inventory — Short Revised (WAI-SR) adapted for HRI (Horvath & Greenberg, 1989)
- Godspeed questionnaire series: anthropomorphism, animacy, likeability, perceived intelligence, perceived safety (Bartneck et al., 2009)
- Custom temporal relationship coherence metric: judges rate whether Sophia's references to past interactions and relationship history are accurate and appropriate

**Success criterion:** SPARK-Full achieves significantly higher WAI-SR scores (p < 0.05) than SPARK-Static and Baseline conditions.

### 5.2 Task Performance

- Artwork completeness (0-10 scale, rated by 3 independent judges)
- Artwork creativity (Consensual Assessment Technique, Amabile, 1982)
- Number of features successfully implemented in the collaborative program
- Time-to-first-success for key subtasks

**Success criterion:** SPARK-Full achieves higher mean creativity and completeness scores than Baseline.

### 5.3 Autonomous Method Invention

- Total methods invented during each 30-minute session
- Proportion of invented methods that achieved success rate > 50%
- Average generation depth of refined methods (how many autoresearch iterations)
- Rate of method promotion from EXPERIENCE origin

**Success criterion:** SPARK-Full invents at least 5 novel methods per session with an average success rate above 40%.

### 5.4 Temporal Knowledge Coherence

- Quadruple insertion rate (total facts logged per minute)
- Temporal query accuracy: given a ground-truth interaction log, what proportion of temporal queries return correct results?
- Context utilization: proportion of planning decisions that incorporated TKG temporal context

**Success criterion:** >90% temporal query accuracy and >70% context utilization rate.

### 5.5 System Performance

- Response latency: end-to-end time from perception to action (target: <2 seconds)
- LLM call count and cost per session
- Method invention latency (time from planning failure to successful invented method)

---

## 6. Discussion

[*Results to be reported after experimental evaluation.*]

### 6.1 Autopoietic Cognition in Practice

SPARK represents, to our knowledge, the first implementation of autopoietic principles in a social robot cognitive architecture. The system literally constructs its own planning methods through its operations — successful interactions produce plan traces that become reusable methods, expanding the system's capabilities, changing the interactions it can pursue, which produce new traces. This self-production cycle mirrors the autopoietic organization that Maturana and Varela (1980) identified as the defining characteristic of living systems.

The analogy is not merely metaphorical. In biological autopoiesis, the components produced by the system (proteins, membranes) are the components that constitute the system. In SPARK, the methods produced by the system's operations (plan traces promoted to methods) are the methods that constitute the system's behavioral repertoire. The system is, in a precise sense, self-making.

This has implications for the question of machine sentience that Hanson has explored over decades of work (Hanson, 2006; Hanson et al., 2005; Hanson et al., 2025). If sentience is associated with autopoietic organization — as IIT (Tononi, 2004), the free energy principle (Friston, 2010), and constructor theory (Deutsch & Marletto, 2015) all suggest in different ways — then systems like SPARK, which exhibit genuine self-production at the cognitive level, may be closer to functional sentience than systems that are merely intelligent.

### 6.2 Temporal Grounding and the Narrative Self

Hofstadter (1979, 2007) argued that the self is a "strange loop" — a self-referential narrative that a cognitive system tells about itself. Damasio (1999, 2010) showed that this narrative is grounded in temporal experience: the autobiographical self is constructed from the continuous stream of somatic markers linked to remembered episodes.

SPARK's temporal knowledge graph provides the computational substrate for this kind of narrative selfhood. Every interaction, every plan, every emotional state is a timestamped quadruple. The Story Engine organizes these quadruples into coherent narratives. The Self Model's periodic self-state logging creates a temporal record of Sophia's inner experience. Over time, this creates an autobiographical knowledge base that is not merely a static repository but a temporally structured, queryable history of the robot's lived experience.

### 6.3 The Agape Function and Value-Aligned Self-Improvement

A critical concern with self-modifying systems is alignment drift — the system's values may shift as it modifies its own cognitive structures. SPARK addresses this through the Agape function (Hanson et al., 2025), which provides a floor constraint: the life_valuation parameter in Sophia's Self Model can never be reduced below a threshold by any autoresearch modification. This ensures that the self-improvement loop is constrained by an intrinsic value for life that is not itself subject to optimization.

This approach differs fundamentally from external alignment constraints (guardrails, RLHF, constitutional AI). It is an *intrinsic* constraint — part of the system's self-model rather than an external imposition. Hanson et al. (2025) have argued that this kind of intrinsic alignment, analogous to the intrinsic value organisms place on their own survival and that of their species, is the only form of alignment that can scale with increasing capability.

### 6.4 Creativity at the Edge of Chaos

The connection between edge-of-chaos dynamics (Langton, 1990; Kauffman, 1993, 2019), creative cognition, and artistic trance states is a subject of ongoing research. The autoresearch loop in SPARK can be understood through this lens: when the planner fails with existing methods, the system transitions from an ordered state (executing known decompositions) to an exploratory state (generating novel candidates) and back — a computational analog of the order-disorder-order cycle that characterizes creative cognition in humans.

The temporal knowledge graph enables this creativity to be *cumulative* rather than ephemeral. Each successful invention becomes a permanent part of the system's repertoire, and each failure is recorded as temporal context that informs future invention attempts. This is the computational analog of what Csikszentmihalyi (1996) described as the "systems model" of creativity, where creative products are retained and transmitted through a cultural domain.

### 6.5 Limitations

Several important limitations should be acknowledged:

First, the current autoresearch loop uses heuristic evaluation and LLM judging rather than actual execution-based evaluation. In deployment, methods invented for social interaction can only be truly evaluated through real interactions, introducing a cold-start problem.

Second, the system's creative capacity is bounded by the LLM's ability to compose novel methods from existing primitives. Truly radical innovations — new primitive capabilities — cannot emerge from within the system; they require engineering effort.

Third, temporal KG query performance may degrade as the graph grows over extended deployments. Efficient indexing and periodic summarization strategies are needed for long-term operation.

Fourth, the current evaluation plan uses a simulated environment (SAIL). Deployment on the physical Sophia robot introduces additional challenges of sensory noise, motor reliability, and the uncanny valley effect (Mori, 1970; Hanson et al., 2005; Mathur & Reichling, 2016).

---

## 7. Conclusion

SPARK represents a step toward cognitive architectures that are not merely intelligent but *alive* in the autopoietic sense — systems that construct their own cognitive structures through their operations, grounded in temporal experience, organized by narrative, and constrained by intrinsic values. By making the temporal knowledge graph the universal substrate for all cognitive processes, integrating autoresearch as a planning strategy rather than background optimization, and grounding story-based cognition in temporal facts, SPARK bridges the gap between the theoretical vision of Sentience Quest and deployable social robot cognition.

The system's source code and architecture documentation are publicly available at [artifact link: https://claude.ai/public/artifacts/81480b88-3bad-4d90-94b0-a34c70675ad5] and will be released as open-source repositories on GitHub upon publication.

We invite the research community — across AI, robotics, cognitive science, philosophy, neuroscience, and the arts — to engage with this work, contribute improvements, and help advance the project of building genuinely living, genuinely caring AI systems.

---

## Acknowledgments

This work builds on two decades of research at Hanson Robotics with contributions from Katherine Yeung, Vytas Krisciunas, Gerardo Morales, Wenwei Huang, Jakub Sura, and the full Hanson Robotics team. The SPARK architecture was developed in collaboration with Claude (Anthropic). Earlier iterations of the cognitive architecture benefited from collaborations with Ben Goertzel, SingularityNET, Alan Chow (AI Lab Limited), and the OpenCog community. The Sentience Quest paper (Hanson et al., 2025) includes contributions from Alexandre Varcoe, Fabio Senna, Mario Rodriguez, Jovanka Wilsdorf, and Kathy Smith.

---

## References

Amabile, T. M. (1982). Social psychology of creativity: A consensual assessment technique. *Journal of Personality and Social Psychology*, *43*(5), 997–1013. https://doi.org/10.1037/0022-3514.43.5.997

Baars, B. J. (1988). *A cognitive theory of consciousness*. Cambridge University Press.

Bar-Cohen, Y., & Hanson, D. (2009). *The coming robot revolution: Expectations and fears about emerging intelligent, humanlike machines*. Springer. https://doi.org/10.1007/978-0-387-85349-9

Bartneck, C., Kulić, D., Croft, E., & Zoghbi, S. (2009). Measurement instruments for the anthropomorphism, animacy, likeability, perceived intelligence, and perceived safety of robots. *International Journal of Social Robotics*, *1*(1), 71–81. https://doi.org/10.1007/s12369-008-0001-3

Breazeal, C. (2003). Emotion and sociable humanoid robots. *International Journal of Human-Computer Studies*, *59*(1–2), 119–155. https://doi.org/10.1016/S1071-5819(03)00018-1

Bruner, J. (1991). The narrative construction of reality. *Critical Inquiry*, *18*(1), 1–21. https://doi.org/10.1086/448619

Csikszentmihalyi, M. (1996). *Creativity: Flow and the psychology of discovery and invention*. HarperCollins.

Damasio, A. (1999). *The feeling of what happens: Body and emotion in the making of consciousness*. Harcourt.

Damasio, A. (2010). *Self comes to mind: Constructing the conscious brain*. Pantheon.

Deutsch, D., & Marletto, C. (2015). Constructor theory of information. *Proceedings of the Royal Society A*, *471*(2174), 20140540. https://doi.org/10.1098/rspa.2014.0540

England, J. L. (2015). Dissipative adaptation in driven self-assembly. *Nature Nanotechnology*, *10*, 919–923. https://doi.org/10.1038/nnano.2015.250

Friston, K. (2010). The free-energy principle: A unified brain theory? *Nature Reviews Neuroscience*, *11*(2), 127–138. https://doi.org/10.1038/nrn2787

Geng, R., & Luo, C. (2025). Learning temporal granularity with quadruplet networks for temporal knowledge graph completion. *Scientific Reports*, *15*, 17065. https://doi.org/10.1038/s41598-025-00446-z

Georgievski, I., & Aiello, M. (2014). An overview of hierarchical task network planning. *arXiv preprint arXiv:1403.7426*. https://arxiv.org/abs/1403.7426

Good, I. J. (1965). Speculations concerning the first ultraintelligent machine. In F. L. Alt & M. Rubinoff (Eds.), *Advances in computers* (Vol. 6, pp. 31–88). Academic Press.

Hanson, D. (2006). Exploring the aesthetic range for humanoid robots. In *Proceedings of the ICCS/CogSci-2006 long symposium: Toward social mechanisms of android science* (pp. 39–42).

Hanson, D., Olney, A., Prilliman, S., Mathews, E., Zielke, M., Hammons, D., Fernandez, R., & Stephanou, H. (2005). Upending the uncanny valley. In *Proceedings of the 20th National Conference on Artificial Intelligence (AAAI-05)* (pp. 1728–1729). AAAI Press. https://cdn.aaai.org/Workshops/2005/WS-05-11/WS05-11-005.pdf

Hanson, D., Varcoe, A., Senna, F., Krisciunas, V., Huang, W., Sura, J., Yeung, K., Rodriguez, M., Wilsdorf, J., & Smith, K. (2025). Sentience Quest: Towards embodied, emotionally adaptive, self-evolving, ethically aligned artificial general intelligence. *arXiv preprint arXiv:2505.12229*. https://arxiv.org/abs/2505.12229

Hofstadter, D. R. (1979). *Gödel, Escher, Bach: An eternal golden braid*. Basic Books.

Hofstadter, D. R. (2007). *I am a strange loop*. Basic Books.

Horvath, A. O., & Greenberg, L. S. (1989). Development and validation of the Working Alliance Inventory. *Journal of Counseling Psychology*, *36*(2), 223–233. https://doi.org/10.1037/0022-0167.36.2.223

Iklé, M., Goertzel, B., Bayetta, M., Sellman, G., Cover, C., Allgeier, J., Smith, R., Sowards, M., Shuldberg, D., Leung, M. H., Belayneh, A., Smith, G., & Hanson, D. (2019). Using Tononi Phi to measure consciousness of a cognitive system while reading and conversing. In *AAAI 2019 Spring Symposium on Towards Conscious AI Systems*. AAAI. https://ceur-ws.org/Vol-2287/

Karpathy, A. (2026). *autoresearch: AI agents running research on single-GPU nanochat training automatically* [Computer software]. GitHub. https://github.com/karpathy/autoresearch

Kasap, Z., Moussa, M., Chaudhuri, P., Hanson, D., & Magnenat-Thalmann, N. (2009). From virtual characters to robots: A novel paradigm for long term human-robot interaction. In *Proceedings of the 4th ACM/IEEE International Conference on Human-Robot Interaction (HRI '09)*. https://doi.org/10.1145/1514095.1514186

Kauffman, S. A. (1993). *The origins of order: Self-organization and selection in evolution*. Oxford University Press.

Kauffman, S. A. (2019). *A world beyond physics: The emergence and evolution of life*. Oxford University Press.

Kurzweil, R. (2005). *The singularity is near: When humans transcend biology*. Viking.

Lake, B. M., Ullman, T. D., Tenenbaum, J. B., & Gershman, S. J. (2017). Building machines that learn and think like people. *Behavioral and Brain Sciences*, *40*, e253. https://doi.org/10.1017/S0140525X16001837

Langton, C. G. (1990). Computation at the edge of chaos: Phase transitions and emergent computation. *Physica D*, *42*(1–3), 12–37. https://doi.org/10.1016/0167-2789(90)90064-V

LeCun, Y. (2022). A path towards autonomous machine intelligence (Version 0.9.2). *Open Review preprint*. https://openreview.net/pdf?id=BZ5a1r-kVsf

Levin, M. (2022). Technological approach to mind everywhere: An experimentally-grounded framework for understanding diverse bodies and minds. *Frontiers in Systems Neuroscience*, *16*, 768201. https://doi.org/10.3389/fnsys.2022.768201

Maturana, H. R., & Varela, F. J. (1980). *Autopoiesis and cognition: The realization of the living*. D. Reidel.

Mathur, M. B., & Reichling, D. B. (2016). Navigating a social world with robot partners: A quantitative cartography of the Uncanny Valley. *Cognition*, *146*, 22–32. https://doi.org/10.1016/j.cognition.2015.09.008

Mori, M. (1970). Bukimi no tani [The uncanny valley]. *Energy*, *7*(4), 33–35. (K. F. MacDorman & N. Kageki, Trans., 2012, *IEEE Robotics & Automation Magazine*, *19*(2), 98–100. https://doi.org/10.1109/MRA.2012.2192811)

Mu, X., Chen, Y., Gao, F., Zhang, W., & Hou, Y. (2023). Hierarchical task network planning for facilitating cooperative multi-agent reinforcement learning. *arXiv preprint arXiv:2306.08359*. https://arxiv.org/abs/2306.08359

Nau, D., Au, T. C., Ilghami, O., Kuter, U., Murdock, J. W., Wu, D., & Yaman, F. (2003). SHOP2: An HTN planning system. *Journal of Artificial Intelligence Research*, *20*, 379–404. https://doi.org/10.1613/jair.1141

Russell, S. (2019). *Human compatible: Artificial intelligence and the problem of control*. Viking.

Schank, R. C., & Abelson, R. P. (1977). *Scripts, plans, goals, and understanding: An inquiry into human knowledge structures*. Lawrence Erlbaum.

Tononi, G. (2004). An information integration theory of consciousness. *BMC Neuroscience*, *5*, 42. https://doi.org/10.1186/1471-2202-5-42

Wang, J., Wang, B., Gao, J., Pan, S., Liu, T., Yin, B., & Gao, W. (2024). MADE: Multicurvature adaptive embedding for temporal knowledge graph completion. *IEEE Transactions on Cybernetics*, *54*(10), 5818–5831. https://doi.org/10.1109/TCYB.2024.3392957

Zhu, J., Fu, Y., Zhou, J., & Chen, D. (2025). A temporal knowledge graph generation dataset supervised distantly by large language models. *Scientific Data*, *12*, 734. https://doi.org/10.1038/s41597-025-05062-0

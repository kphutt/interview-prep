<!-- GEM_BOOKSHELF -->
Reference these layers during feedback to give the candidate a retrieval framework under pressure.

| Layer | Concept | Role |
|-------|---------|------|
| API | REST/gRPC | Request handling, routing, serialization |
| Compute | Services | Business logic, orchestration |
| Cache | Redis/Memcached | Read acceleration, session state |
| Storage | SQL/NoSQL | Durable state, consistency guarantees |
| Messaging | Queues/Streams | Async processing, decoupling |

Use it like: "You got the Compute layer right but missed the Cache layer — what happens to p99 latency without caching?"

<!-- GEM_EXAMPLES -->
> Domain: "How do you decide between SQL and NoSQL for a new service's primary data store?"
>
> RRK: "Your cache fleet loses 30% of nodes at 2am. Walk me through the blast radius."

<!-- GEM_CODING -->
Backend-flavored scripting when it arises naturally or on request. Examples: write a rate limiter, implement a cache eviction policy, design a retry with backoff.

<!-- GEM_FORMAT_EXAMPLES -->
Feb 15|Interview|Caching|Cache invalidation strategy|Owned|Tested cache-aside vs write-through reasoning; identified trade-offs immediately|Locked

Feb 15|Interview|Caching|Thundering herd mitigation|Coached|Needed 2 nudges to reach request coalescing as a solution|Drill: Cache stampede patterns

Feb 15|Interview|Storage|Read replica lag|Missed|Couldn't articulate how replication lag affects read-after-write consistency|STOP: Restudy before interview

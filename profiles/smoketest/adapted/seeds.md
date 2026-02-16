<!-- DOMAIN_SEEDS -->
Use the following example as the definition for depth and content.

---

### Episode 1: The Cache Invalidation Problem
**Focus:** Consistency vs. Performance trade-offs in caching layers
**Mental Model:** "A library card catalog that's always slightly out of date."
**The L4 Trap:** "Just set a short TTL." (Creates thundering herd on expiry; doesn't solve stale reads during writes).
**The Nitty Gritty:**
- **Cache-aside:** App checks cache first, falls back to DB, populates cache on miss. Simple but prone to stale data on writes.
- **Write-through:** Write to cache and DB together. Consistent but adds write latency.
- **Invalidation signals:** Pub/sub from DB change stream to cache nodes. Reduces staleness window to propagation delay.
**The Staff Pivot:** "Cache-aside for read-heavy, write-through for consistency-critical. Measure: cache hit rate, p99 read latency, stale-read rate."

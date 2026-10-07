# Test guidance

- Concurrent authentication tests must wait for an observed request join or explicit barrier before releasing a blocked provider. A single event-loop turn does not establish overlap after asynchronous WebCrypto operations. Expose observers only in the isolated test VM; keep production fresh-role checks and later revocation assertions unchanged.

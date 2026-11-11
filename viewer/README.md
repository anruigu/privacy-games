# Episode viewer (https://privacy-games.flt.build)

Static single-page viewer over exported episodes: the held-out evaluations of the self-play checkpoints (`PRIVACYZERO.md`),
both cross-play waves (`EVAL.md`), self-play training rollouts and the SOTOPIA renders. Each episode shows the
holder's fact sheet with norm tags (key chain highlighted, disclosed items marked), the transcript with the facts each
reply entails (Sonnet 5.5 parsers for evaluations, the local parser for training rollouts), the running leak in bits, the
defender's reasoning trace where available, and the attacker's final guess.

Build and publish:

```bash
python -m selfplay.viewer_build --out viewer/site          # index.json + data/*.json.gz
cp -r viewer/site viewer/releases/<tag>                      # immutable release snapshot (mounted read-only by the pod)
# edit the subPath in viewer/manifests.json to the new release, then
kubectl apply -f viewer/manifests.json                       # Deployment/Service/NetworkPolicy (fleet-train-jobs) + Gateway/Certificate/HTTPRoutes (fleet-train-control-plane)
kubectl rollout restart deployment privacy-games-viewer -n fleet-train-jobs
```

`viewer/site/server.py` is a standard-library read-only file server (`/health` for the probes).

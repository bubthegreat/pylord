# Deploying pylord

The realm runs on the homelab k3s cluster as a Helm release, delivered by
ArgoCD. Nothing is applied by hand: CI builds the image, writes the new tag
into `values/prod.yaml`, and Argo rolls it out.

```
deploy/
  helm/pylord/     the chart (the only place manifests are defined)
  values/          per-environment values: local.yaml, prod.yaml
  argocd/          the Application manifest to register in homelab-app-config
```

## Layout decisions

- **One chart, values per environment.** The previous convention in this
  homelab was kustomize overlays (see `kbk`); this is the Helm equivalent,
  and Argo renders it the same way.
- **A browser terminal is how the realm is reachable from outside.** An
  HTTP `Ingress` cannot carry telnet -- nginx Ingress objects route
  HTTP(S) only -- and this cluster's only externally-reachable address is
  the ingress-nginx LoadBalancer on 80/443. So the pod runs a `ttyd`
  sidecar (from the same image) driving a telnet client against the game
  over loopback, and the Ingress points at that: `https://lord.bubtaylor.com`,
  TLS from `letsencrypt-prod`. Telnet clients still connect directly to
  the MetalLB address on the LAN.

  (Worth knowing: `kbk`'s `tcp-services` ConfigMap is inert -- the
  controller has no `--tcp-services-configmap` argument and its Service
  exposes only 80/443 -- so that pattern does not currently reach the
  outside world either.)
- **LoadBalancer, not the shared nginx TCP ConfigMap.** Telnet needs a raw
  TCP port. `kbk` routes it through `ingress-nginx`'s `tcp-services`
  ConfigMap, which means editing a cluster-wide object owned by another
  Argo app for every new game. MetalLB is available (`general-pool`,
  192.168.0.41-100), so pylord takes its own address instead and touches
  nothing shared. Set `service.type: ClusterIP` and add a `tcp-services`
  entry if you'd rather have the nginx route.
- **MySQL, not SQLite.** The realm ran on a SQLite file on a
  ReadWriteOnce volume, which pinned the game pod to one node, made every
  deploy a full stop-and-start, and left backups to "copy the file and hope
  nobody was mid-write". MySQL runs as its own Deployment in this chart and
  owns the volume; the game pod holds nothing.
- **The database volume outlives the release** -- but the reclaim policy is
  what actually saves it. The PVC carries `helm.sh/resource-policy: keep`
  and `argocd.argoproj.io/sync-options: Delete=false`, and during the MySQL
  move those did *not* stop Argo pruning the old `pylord-data` PVC once the
  chart stopped rendering it. `longhorn-retain` did: the PV survived as
  `Released`, with the realm intact and re-bindable. Treat the annotations
  as a courtesy and the `Retain` reclaim policy as the actual guarantee.
- **One replica, `maxSurge: 0`.** Not a storage limit any more -- the daily
  maintenance pass and the "already adventuring elsewhere" login check are
  not yet guarded across processes, so two game pods would both roll the
  day over. Fix those and the replica count can go up.
- **The password is a Secret, not the ConfigMap.** The game reads a whole
  SQLAlchemy URL from `PYLORD_DB_URL`, so the credential never appears in
  the rendered `config.toml`.
- **The chart never generates a password.** Argo re-renders it on every
  sync with no view of the cluster, so a generated one would rotate
  underneath a running database and lock the game out. Create the Secret
  out of band (below) and point `mysql.auth.existingSecret` at it.
- **IGMs ship in the image.** They were briefly copied onto a volume on
  first start, which meant a fix to a bundled IGM could never reach a realm
  that had already been seeded -- the stale copy kept loading, and a
  daily-limit fix sat unused in production for a day. IGMs are code: they
  arrive with a release.

## First-time setup

1. **Docker Hub token** — add a `DOCKER_HUB_TOKEN` repository secret to
   `bubthegreat/pylord` (Settings → Secrets → Actions) so the build
   workflow can push `bubthegreat/pylord`.

2. **Create the database Secret** — the chart will refuse to render
   without one:

   ```sh
   kubectl -n pylord-prod create secret generic pylord-db \
     --from-literal=password="$PW" \
     --from-literal=root-password="$ROOT_PW" \
     --from-literal=url="mysql+aiomysql://lord:$PW@pylord-mysql:3306/lord?charset=utf8mb4"
   ```

   then set `mysql.auth.existingSecret: pylord-db` in `values/prod.yaml`.

3. **Register the app with Argo** — copy the Application into the GitOps
   repo and commit:

   ```sh
   cp deploy/argocd/pylord-prod.yaml ../homelab-app-config/apps/
   cd ../homelab-app-config && git add apps/pylord-prod.yaml \
     && git commit -m "feat: deploy pylord to prod" && git push
   ```

   The root app (`app-config-root`) recurses `apps/`, so the realm appears
   within a sync cycle. Watch it:

   ```sh
   kubectl -n argocd get application pylord-prod -w
   ```

4. **Play**:

   - From anywhere: <https://lord.bubtaylor.com>
   - From the LAN, with a real telnet client:

     ```sh
     kubectl -n pylord-prod get svc pylord \
       -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
     telnet <that address> 2323
     ```

## Day-to-day

| Task | How |
|------|-----|
| Ship a change | Merge to `main`. The release workflow runs the suite, builds the image, pins the chart at the next patch version, and tags it. Argo tracks `>=0.1.0` over those tags, so the tag is the deploy. |
| Cut a release by hand | Run the **Release** workflow from the Actions tab (`workflow_dispatch`). |
| Change a game knob | Edit `values/prod.yaml`'s `game:` block and push — the config checksum restarts the pod. |
| Roll back | `argocd app rollback pylord-prod`, or delete the bad tag so Argo resolves the previous one: `git push origin :refs/tags/vX.Y.Z`. |
| Sysop CLI | `kubectl -n pylord-prod exec deploy/pylord -- pylord players --config /config/config.toml` |
| Back up the realm | `kubectl -n pylord-prod exec deploy/pylord-mysql -- sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction lord' > lord.sql` -- `--single-transaction` matters: it takes a consistent snapshot without locking players out mid-session. Longhorn also snapshots the volume. |
| Restore | `kubectl -n pylord-prod exec -i deploy/pylord-mysql -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" lord' < lord.sql` |
| Open a SQL shell | `kubectl -n pylord-prod exec -it deploy/pylord-mysql -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" lord'` |

## Local development

`tilt up` runs the same chart against a local cluster with
`values/local.yaml` (ClusterIP + port-forward on 2323, a small volume, and a
one-minute fight-regeneration clock so the timer is quick to watch). Editing
anything under `pylord/` or `igms/` live-syncs into the pod; changing
dependencies rebuilds the image.

Without a cluster, `uv run pylord serve` and `uv run pylord smoke` need
nothing but the repo.

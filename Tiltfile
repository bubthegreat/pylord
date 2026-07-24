# Local pylord loop: build the image, run the same Helm chart the homelab
# runs, forward the telnet port.
#
#   tilt up          # then: telnet localhost 2323
#
# The chart is deployed with deploy/values/local.yaml (ClusterIP, small
# volume, one-minute fight regeneration so the clock is quick to watch).
# The realm's volume survives `tilt down` -- see the PVC's
# tilt.dev/down-policy annotation.

allow_k8s_contexts(['docker-desktop', 'kind-kind', 'minikube', 'rancher-desktop'])

docker_build(
    'bubthegreat/pylord',
    context='.',
    dockerfile='Dockerfile',
    # The scenes are pure Python: sync them in and restart rather than
    # rebuilding the image. A dependency change still triggers a full build,
    # because pyproject.toml/uv.lock are not synced.
    live_update=[
        sync('./pylord/', '/app/pylord/'),
        sync('./igms/', '/app/igms/'),
    ],
    ignore=['tests/', 'reference/', 'docs/', 'deploy/', '*.db*'],
)

k8s_yaml(
    helm(
        'deploy/helm/pylord',
        name='pylord',
        values=['deploy/values/local.yaml'],
        set=['image.repository=bubthegreat/pylord', 'image.tag=dev'],
    )
)

k8s_resource(
    workload='pylord',
    # 2323 for a telnet client, 7681 for the browser terminal the homelab
    # serves over HTTPS.
    port_forwards=['2323:2323', '7681:7681'],
    labels=['game'],
)

# Handy buttons: the sysop CLI against the running realm.
local_resource(
    'players',
    cmd='kubectl exec deploy/pylord -- pylord players --config /config/config.toml',
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
    resource_deps=['pylord'],
    labels=['ops'],
)

# The same end-to-end walkthrough CI runs, against a throwaway server.
local_resource(
    'smoke',
    cmd='uv run pylord smoke',
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
    labels=['ops'],
)

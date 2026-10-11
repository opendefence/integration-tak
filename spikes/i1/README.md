# I1 binary component probe

This probe executes authentication and contact classes from the TAK 5.8.84 WAR.
It generates four temporary certificates and starts one local Ignite node.
The probe runs in a disposable container with no network.
It leaves private keys and generated certificates in the container tmpfs.

The artifact directory must contain `takserver.war` from the tested server image.
Set `PROBE_ARTIFACTS` to that directory and run:

```sh
podman run --rm --network none --cpus 2 --memory 4g \
  --tmpfs /work:rw,size=3g \
  -v "$PROBE_ARTIFACTS:/artifacts:ro" \
  -v "$PWD/spikes/i1:/probe:ro" \
  eclipse-temurin:17-jdk-noble@sha256:fb79620c3f6ee8f1c7530a8dc4fd49e3b410bcef037694ad4858a1553bac4170 \
  sh /probe/probe.sh
```

The probe must print `approved_set_requirement=FAIL` for the current binary.
That result means the unapproved same-UUID certificate received the configured role and groups.
The probe also calls the actual `SubmissionService.processContactMessage` method through reflection.
It parses a CoT fixture and proves that `CLIENT-NEXT` replaces the contact name `DESIRED`.
The fixture certificate and account permissions remain unchanged. No subscription exists in this fixture.
See `docs/i1-findings.md` for the tested tuple and interpretation.

This is a component probe.
It does not start a live TAK server or prove TLS, network CoT delivery, restart, or client behavior.
The private contact handler runs without server initialization, routing, or UID authentication.
Keep it out of production images.

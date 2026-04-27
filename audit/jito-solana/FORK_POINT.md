# Jito-Solana Fork Point

## Repository

- URL: https://github.com/jito-foundation/jito-solana
- HEAD commit: `d18e1be6924969b6fea1e0d417d38225b0d80224`
- HEAD date: 2026-04-23
- HEAD message: `[Master] Poh Core ordering (#1427)`
- Latest tag: `v4.0.0-beta.7-jito`

## Upstream Agave Base

- Based on Agave `v4.0.0-beta.7`
- Fork divergence: Jito adds the `bundle/`, `jito-protos/`, `bam-*`, `votor/`, `votor-messages/`, `core/src/bundle_stage*`, `core/src/tip_manager*`, `core/src/proxy/` directories

## Clone Method

```
git clone --depth=1 --branch master https://github.com/jito-foundation/jito-solana.git
```

## Jito-only Top-level Directories

- `bundle/` — Bundle ID derivation
- `jito-protos/` — gRPC protobuf definitions for block engine, relayer, auth
- `bam-client/` — Block Auction Marketplace client
- `bam-types/` — BAM gRPC types
- `votor/` — Validator-specific consensus additions
- `votor-messages/` — Votor messaging protocol

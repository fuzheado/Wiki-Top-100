# Deploying to Wikimedia Toolforge

This guide deploys WikiTop100 as a **build service** container on Toolforge using Cloud Native Buildpacks. No code changes are needed beyond what's already committed.

## Prerequisites

- A [Toolforge account](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Quickstart) with SSH access
- The tool name registered (e.g. `my-tool`) via [toolsadmin](https://toolsadmin.wikimedia.org/)

## One-time Setup

### 1. Create the service template

SSH to the bastion and write `$HOME/service.template`:

```bash
ssh <username>@login.toolforge.org
become my-tool
```

```yaml
# /data/project/my-tool/service.template
cpu: 500m
mem: 1Gi
type: buildservice
mount: none
health-check-path: /
```

1Gi memory is recommended because spaCy + graph assembly needs more than the default 512Mi.

### 2. Build and start

Build the container image directly from the public git repo — no clone needed:

```bash
toolforge build start https://github.com/fuzheado/Wiki-Top-100
```

Watch the build log:
```bash
toolforge build logs --follow
```

Once the build succeeds, start the webservice:
```bash
toolforge webservice --template=$HOME/service.template start
```

Your tool is now live at **https://my-tool.toolforge.org**.

### 3. Set environment variables

```bash
toolforge envvars set WIKI_USER_AGENT="WikiTop100Viz/1.0 (contact: your-email@example.com)"
```

The User-Agent is required by Wikimedia API policy. You can also set `WIKI_MAX_CONCURRENT`, `WIKI_CACHE_DIR`, etc. (see `.env.example`).

## Updating

```bash
become my-tool
toolforge build start https://github.com/fuzheado/Wiki-Top-100
toolforge webservice restart
```

The build service pulls the latest code from the repo, rebuilds the image, then a restart picks it up.

## Logs

```bash
toolforge webservice logs         # recent logs
toolforge webservice logs -f      # follow in real-time
```

## Troubleshooting

| Symptom | Likely fix |
|---------|-----------|
| Pod crashes on start | Check logs: `toolforge webservice logs`. Common cause: out of memory — bump `mem: 1Gi` in `service.template` |
| Build fails | `toolforge build logs --follow` to see where it failed. Common cause: network timeout downloading spaCy model — retry the build |
| "No data for this date" in UI | The Hatnote API may not have data for that date yet, or the date format is wrong |
| 502 Bad Gateway | The container may be taking too long to start. Check `toolforge webservice status` and logs |
| Rate-limited by MW API | Set `WIKI_MAX_CONCURRENT=2` and a proper `WIKI_USER_AGENT` with your contact email |

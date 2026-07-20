# astro-template

A minimal, production-ready template for starting [Astro](https://astro.build) website projects.

## Features

- ⚡ **Minimal Astro setup** — static by default, fast and SEO-friendly
- 🚀 **GitHub Actions** — automatic build on every push; one-click deploy to GitHub Pages
- ⚙️ **[dotconfig](https://github.com/ericbusboom/dotconfig)** — layered environment configuration (dev / prod / local overrides)
- 🐳 **[rundbat](https://github.com/ericbusboom/rundbat)** — Docker-based deployment management for testing and production
- 📜 **Setup scripts** — get from clone to running in minutes

---

## Quick Start

```bash
# 1. Clone or fork this template
git clone https://github.com/your-org/your-project.git
cd your-project

# 2. Run the setup script (installs deps, creates local config)
./scripts/setup.sh

# 3. Start the dev server
npm run dev
# → open http://localhost:4321
```

---

## Project Structure

```
astro-template/
├── .github/
│   └── workflows/
│       ├── build.yml       # Build on every push / PR
│       └── deploy.yml      # Deploy to GitHub Pages on push to main
├── config/                 # dotconfig configuration tree
│   ├── sops.yaml           # SOPS encryption rules (edit with your age key)
│   ├── rundbat.yaml        # rundbat project config
│   ├── dev/
│   │   └── public.env      # Public dev environment variables
│   ├── prod/
│   │   └── public.env      # Public prod environment variables
│   └── local/
│       └── example/
│           └── public.env  # Template for personal local overrides
├── docker/
│   ├── Dockerfile          # Multi-stage build → Nginx static server
│   └── docker-compose.yml  # Docker Compose for local/Docker deployment
├── scripts/
│   ├── setup.sh            # First-time setup
│   ├── dev.sh              # Start dev server (with optional dotconfig load)
│   └── docker-run.sh       # Build and run in Docker
├── src/
│   ├── layouts/
│   │   └── Layout.astro    # Base HTML layout
│   └── pages/
│       └── index.astro     # Home page
├── public/
│   └── favicon.svg
├── astro.config.mjs
├── package.json
└── tsconfig.json
```

---

## GitHub Pages Deployment

1. In your repository settings → **Pages**, set the source to **GitHub Actions**.
2. Push to `main` — the `deploy.yml` workflow builds and publishes the site automatically.
3. Update `astro.config.mjs` with your `site` and `base` if needed:

```js
export default defineConfig({
  site: 'https://your-username.github.io',
  base: '/your-repo-name',
});
```

---

## Configuration with dotconfig

This template uses [dotconfig](https://github.com/ericbusboom/dotconfig) to manage a layered `.env` file from multiple source files.

### Install dotconfig

```bash
pipx install dotconfig
```

### Configuration layout

```
config/
  dev/public.env           ← committed public vars for dev
  prod/public.env          ← committed public vars for prod
  local/<yourname>/        ← your personal overrides (gitignored)
    public.env
    secrets.env            ← SOPS-encrypted secrets (optional)
  sops.yaml                ← SOPS key rules
```

### Setup your local config

```bash
# Copy the example local config
cp -r config/local/example config/local/<yourname>
# Edit your overrides
$EDITOR config/local/<yourname>/public.env

# Generate .env
dotconfig load -d dev -l <yourname>
```

### Load / save config

```bash
# Load dev config with your local overrides
dotconfig load -d dev -l <yourname>

# Load prod config
dotconfig load -d prod

# After editing .env directly, save it back to the source files
dotconfig save
```

The generated `.env` is gitignored — the source files in `config/` are what you commit.

---

## Docker Deployment with rundbat

[rundbat](https://github.com/ericbusboom/rundbat) manages Docker-based deployment environments.

### Install rundbat

```bash
pipx install rundbat
```

### Quick Docker commands

```bash
# Detect environment
rundbat discover

# Initialize rundbat in this project
rundbat init

# Build and run in Docker via helper script
./scripts/docker-run.sh up       # start (builds image first)
./scripts/docker-run.sh down     # stop
./scripts/docker-run.sh logs     # follow logs

# Or use rundbat directly
rundbat start dev
rundbat stop dev
rundbat health dev
```

The site will be available at `http://localhost:8080` by default.

### Adding a database

If your project needs a database, uncomment the `db` service in `docker/docker-compose.yml`, then use rundbat to provision and manage it:

```bash
rundbat add-service postgres
rundbat create-env dev
rundbat get-config dev    # prints the DATABASE_URL
```

---

## Scripts Reference

| Script | Purpose |
|---|---|
| `./scripts/setup.sh [name]` | First-time setup: install deps, create local config, discover rundbat |
| `./scripts/dev.sh [name]` | Load dotconfig and start the Astro dev server |
| `./scripts/docker-run.sh [up\|down\|build\|logs]` | Manage Docker containers |

---

## Customization

- **Add pages**: create `.astro` (or `.md`) files in `src/pages/`
- **Add components**: place reusable components in `src/components/`
- **Add integrations**: `npx astro add <integration>` (e.g., `tailwind`, `react`, `mdx`)
- **Add a backend**: uncomment the `db` service in `docker/docker-compose.yml` and configure rundbat

---

## License

MIT 

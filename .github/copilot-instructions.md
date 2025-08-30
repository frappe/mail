# Frappe Mail Development Instructions

Frappe Mail is a powerful email management system built on the Frappe framework with a Vue.js frontend. Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Development Environment Setup

**CRITICAL: Use Docker for Development (Recommended)**
1. Download the Docker setup files:
   ```bash
   wget -O docker-compose.yml https://raw.githubusercontent.com/frappe/mail/develop/docker/docker-compose.yml
   wget -O init.sh https://raw.githubusercontent.com/frappe/mail/develop/docker/init.sh
   ```

2. Start the development environment:
   ```bash
   docker compose up -d
   ```
   - NEVER CANCEL: Docker setup takes 15-30 minutes on first run. Set timeout to 45+ minutes.
   - The setup downloads images, creates Frappe bench, installs Mail app, and starts services
   - **WARNING**: Docker setup may fail on first attempt due to dependency issues. This is a known limitation.
   - Access the application at http://mail.localhost (if setup succeeds)

3. Default credentials:
   - **Username:** `administrator`
   - **Password:** `admin`

**Frontend-Only Development (Alternative)**
For frontend development without full backend setup:
```bash
cd frontend && yarn dev
```
- Starts Vite dev server on http://localhost:8080
- Works without Frappe backend but with limited functionality
- Useful for UI development and testing

**Manual Frappe Bench Setup (Alternative)**
If Docker is not available, use manual bench setup:
```bash
pip install frappe-bench
bench init --skip-redis-config-generation frappe-bench
cd frappe-bench
bench get-app mail https://github.com/frappe/mail.git --branch develop
bench new-site site1.local --mariadb-root-password root --admin-password admin
bench --site site1.local install-app mail
bench start
```
- NEVER CANCEL: Manual setup takes 10-20 minutes. Set timeout to 30+ minutes.
- Requires MariaDB and Redis running locally

### Building the Application

**Install Dependencies:**
```bash
yarn install
```
- Takes ~50 seconds. Set timeout to 120+ seconds.
- Installs both root and frontend dependencies automatically via postinstall hook

**Build Process (Only works within Frappe bench context):**
```bash
yarn build
```
- NEVER CANCEL: Build takes 2-5 minutes. Set timeout to 10+ minutes.
- Builds both frontend (Vue.js/Vite) and email CSS (Tailwind)
- Requires `common_site_config.json` from Frappe bench
- Build will fail if run outside of Frappe bench context

**Frontend Development Mode:**
```bash
cd frontend && yarn dev
```
- Starts Vite dev server with hot reload
- Access at http://localhost:3000 (proxies to Frappe backend)

### Testing

**Python Tests:**
```bash
# Within Frappe bench:
bench --site site1.local run-tests --app mail
# Or specific test:
bench --site site1.local run-tests --app mail --module mail.mail.doctype.mail_queue.test_mail_queue
```
- NEVER CANCEL: Full test suite takes 5-15 minutes. Set timeout to 30+ minutes.
- Tests use Frappe's test framework (IntegrationTestCase, UnitTestCase)
- Requires active Frappe site with database
- **NOTE**: Most test files are currently stubs without actual test methods

**Frontend Tests:**
- No automated frontend tests currently configured
- Manual testing required through UI

### Linting and Code Quality

**Python Linting:**
```bash
ruff check .
ruff check . --fix  # Auto-fix issues
ruff format .       # Format code
```
- Very fast, usually completes in under 1 second
- Configured via pyproject.toml

**JavaScript/Vue Linting:**
```bash
yarn eslint . --fix
```
- Takes 20-30 seconds. Set timeout to 60+ seconds.
- **WARNING**: Shows errors in generated files (PWA service worker in mail/public/frontend/) - these can be ignored
- Focus on fixing errors in source files (frontend/src/, mail/mail/, etc.)
- Configured via eslint.config.mjs

**Pre-commit Hooks (Optional but Recommended):**
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```
- NEVER CANCEL: First run takes 5-10 minutes to set up environments. Set timeout to 15+ minutes.
- **WARNING**: May fail due to network timeouts or dependency issues in sandboxed environments
- Subsequent runs are much faster (1-2 minutes)
- Runs ruff, eslint, prettier, and other checks
- **Alternative**: Run individual linting tools directly if pre-commit fails

### Validation Scenarios

After making changes, ALWAYS validate through these scenarios:

**Basic Development Validation:**
1. Install dependencies: `yarn install` (~50 seconds)
2. Run linting: `ruff check . --fix && yarn eslint . --fix`
3. Format code: `ruff format .`
4. Start frontend dev server: `cd frontend && yarn dev` (verify it starts on port 8080)

**Build Validation (Requires Frappe Bench):**
1. Ensure you're in a Frappe bench environment
2. Build the application: `yarn build` (2-5 minutes)
3. Verify no build errors (ignore ESLint warnings in generated files)

**Full Functional Validation (Requires Complete Setup):**
1. Access the Mail UI at `/mail` or http://mail.localhost
2. Test login with default credentials (administrator/admin)
3. Navigate to Compose and create a test email
4. Verify the email appears in the Outgoing Mail queue
5. Check that the interface is responsive and functional
6. Test domain and account management features

**Code Quality Validation:**
- Verify no Python syntax errors: `python3 -m py_compile mail/mail/*.py`
- Check for common issues: `ruff check .`
- **NOTE**: TypeScript compilation (`npx tsc --noEmit`) has many dependency errors - focus on source file errors only

## Project Structure

### Key Directories
```
/                    # Root with package.json, pyproject.toml
├── mail/            # Python Frappe app
│   ├── api/         # API endpoints
│   ├── mail/        # Core email functionality
│   └── public/      # Static assets
├── frontend/        # Vue.js frontend application
│   ├── src/         # Vue source code
│   └── package.json # Frontend dependencies
├── .github/         # GitHub Actions workflows
└── docker/          # Docker development setup
```

### Important Files
- `package.json` - Root build scripts and dev dependencies
- `frontend/package.json` - Frontend dependencies (Vue, Vite, etc.)
- `pyproject.toml` - Python dependencies and ruff configuration
- `.pre-commit-config.yaml` - Pre-commit hook configuration
- `eslint.config.mjs` - ESLint configuration for JavaScript/Vue
- `.github/workflows/ci.yml` - CI pipeline with tests
- `.github/workflows/linter.yml` - Linting pipeline

**Common Issues and Solutions

**Build Failures:**
- "Could not resolve common_site_config.json" - Must build within Frappe bench context
- ESLint errors in generated files (mail/public/frontend/) - These are expected, focus on source files
- TypeScript compilation errors - Many are from dependencies, focus on src/ directory errors

**Development Setup:**
- Docker taking too long - Be patient, first setup downloads large images
- Docker setup failing - Known issue with dependency conflicts, try manual bench setup
- Database connection errors - Ensure MariaDB and Redis are running
- Permission errors - Check file permissions in Docker volumes

**Linting Issues:**
- Pre-commit hooks failing - Use individual linting tools directly (ruff, eslint)
- Network timeouts during pre-commit - Expected in sandboxed environments
- ESLint errors in node_modules - Ignore, focus on source code

### Quick Start for Common Tasks

**Making Frontend Changes:**
1. `cd frontend && yarn dev` - Start development server
2. Edit files in `frontend/src/`
3. `yarn eslint frontend/ --fix` - Lint your changes
4. Test in browser at http://localhost:8080

**Making Backend Changes:**
1. Edit files in `mail/mail/`
2. `ruff check . --fix && ruff format .` - Lint and format
3. `python3 -m py_compile mail/mail/*.py` - Check syntax
4. Restart Frappe server to test (if running)

**Before Committing:**
```bash
ruff check . --fix
ruff format .
yarn eslint . --fix
# Test your changes manually
```

- **yarn install**: ~50 seconds (set timeout: 120+ seconds)
- **yarn build**: 2-5 minutes (set timeout: 10+ minutes)
- **Docker setup**: 15-30 minutes first time (set timeout: 45+ minutes)
- **Manual bench setup**: 10-20 minutes (set timeout: 30+ minutes)
- **Full test suite**: 5-15 minutes (set timeout: 30+ minutes)
- **Pre-commit first run**: 5-10 minutes (set timeout: 15+ minutes)
- **Linting (ruff)**: <1 second
- **Linting (eslint)**: 20-30 seconds (set timeout: 60+ seconds)

## CI/CD Pipeline

The project uses GitHub Actions for:
- **CI** (`.github/workflows/ci.yml`): Full test suite with MariaDB and Redis
- **Linter** (`.github/workflows/linter.yml`): Pre-commit hooks and security scans

Always run `ruff check . --fix && yarn eslint . --fix` before committing to avoid CI failures.
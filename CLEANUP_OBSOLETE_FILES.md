# Obsolete Files to Remove

The following directories and files are **obsolete** and can be safely deleted. They were part of the initial Ruby plugin approach, which has been replaced by the browser extension.

## Ruby Plugin Files (Obsolete)

These were for a Redmine plugin that is no longer needed:

```bash
# Remove Ruby plugin directories
rm -rf app/
rm -rf lib/
rm -rf spec/

# Remove Ruby plugin files
rm -f init.rb
rm -f Gemfile
rm -f test_ruby_client.rb
rm -f test_scrapers.rb
rm -f setup.sh

# Remove old documentation
rm -f STAGE1_SUMMARY.md
rm -f STAGE1_PYTHON_COMPLETE.md
```

## Why These Are Obsolete

1. **app/** - Redmine controller (replaced by browser extension)
2. **lib/** - Ruby scrapers and client (replaced by Python service)
3. **spec/** - Ruby tests (not needed)
4. **init.rb** - Redmine plugin initialization (not needed)
5. **Gemfile** - Ruby dependencies (not needed)
6. **test_ruby_client.rb** - Ruby client tests (not needed)
7. **test_scrapers.rb** - Ruby scraper tests (not needed)
8. **setup.sh** - Ruby setup script (not needed)
9. **STAGE1_*.md** - Old documentation (superseded by current docs)

## What to Keep

✅ **python_service/** - Backend API (REQUIRED)
✅ **browser_extension/** - Frontend extension (REQUIRED)
✅ **README.md** - Main documentation
✅ **ARCHITECTURE.md** - System design
✅ **BROWSER_EXTENSION_GUIDE.md** - Installation guide
✅ **QUICK_START.md** - Setup guide
✅ **.gitignore** - Git configuration
✅ **.vscode/** - VSCode settings

## Clean Up Command

Run this to remove all obsolete files:

```bash
# From project root
rm -rf app/ lib/ spec/
rm -f init.rb Gemfile test_ruby_client.rb test_scrapers.rb setup.sh
rm -f STAGE1_SUMMARY.md STAGE1_PYTHON_COMPLETE.md GITHUB_TOKEN_SETUP.md

echo "Cleanup complete! Only browser extension and Python service remain."
```

## After Cleanup

Your project structure will be clean:

```
watsonx-ceph-l3-north-america/
├── python_service/          # Backend API
├── browser_extension/       # Frontend extension
├── README.md               # Main docs
├── ARCHITECTURE.md         # Design docs
├── BROWSER_EXTENSION_GUIDE.md
├── QUICK_START.md
├── .gitignore
└── .vscode/
```

Much cleaner and easier to maintain!

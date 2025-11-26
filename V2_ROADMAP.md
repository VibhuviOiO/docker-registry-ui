# Docker Registry UI v2.0 - Development Roadmap

## 🎯 Goal
Build Harbor-like features with improved UX, keeping it lightweight and database-free.

## ✅ v1.0 Features (Completed)
- Multi-registry support
- Read-only/Read-write modes
- Tag deletion with GC instructions
- Repository statistics
- Docker Hub-style UI (size, digest, timestamps)
- Health checks
- Production-ready deployment

## 🚀 v2.0 Features (In Progress)

### 1. Copy Commands ⏳
- Copy docker pull commands
- Copy digest references
- Copy GC commands
- Clipboard API integration

### 2. Tag Sorting/Filtering ⏳
- Sort by: name, size, date
- Filter by date range
- Show only latest N tags
- Advanced search

### 3. Image Vulnerability Scanning ⏳
- Integrate Trivy scanner
- Show vulnerability badges (Critical/High/Medium/Low)
- Scan on-demand or scheduled
- Export scan reports

### 4. Manifest Viewer ⏳
- View raw manifest JSON
- Show layer details
- Platform/architecture info
- Config blob viewer

### 5. Bulk Operations ⏳
- JSON-based cleanup rules
- Delete tags older than X days
- Regex-based tag deletion
- Keep last N tags
- Dry-run mode

### 6. Usage Analytics ⏳
- Storage usage per repository
- Tag count trends
- Most/least used images
- Charts with Chart.js

### 7. Export/Import ⏳
- Export catalog to JSON/CSV
- Generate reports
- Import cleanup rules

### 8. Dark Mode ⏳
- Theme toggle
- Persist preference
- System theme detection

## 📁 New Structure

```
templates/
├── base.html              # Base layout
├── components/            # Reusable components
│   ├── navbar.html
│   ├── sidebar.html
│   ├── footer.html
│   └── modals.html
└── views/                 # Page views
    ├── repositories.html
    ├── registry_config.html
    ├── cleanup.html
    ├── vulnerabilities.html
    ├── analytics.html
    └── bulk_operations.html
```

## 🔧 Technical Stack

- **Backend**: Python Flask + Uvicorn
- **Frontend**: Bootstrap 5 + Vanilla JS
- **Scanning**: Trivy (Apache 2.0)
- **Charts**: Chart.js
- **Icons**: Bootstrap Icons
- **No Database**: File-based storage

## 📝 Development Phases

### Phase 1: Foundation (Week 1)
- ✅ Create v2.0 branch
- ✅ Restructure templates (modular HTML)
- ✅ Add dark mode toggle
- ✅ Implement copy commands

### Phase 2: Core Features (Week 2)
- ✅ Tag sorting/filtering
- ✅ Manifest viewer
- ⏳ Bulk operations with rules

### Phase 3: Advanced Features (Week 3)
- ⏳ Trivy integration
- ⏳ Vulnerability scanning UI
- ⏳ Usage analytics

### Phase 4: Polish (Week 4)
- ⏳ Export/Import
- ⏳ Performance optimization
- ⏳ Documentation
- ⏳ Testing

## 🎨 Design Principles

1. **Keep it Simple** - No database, minimal dependencies
2. **Performance First** - Lazy loading, efficient API calls
3. **User-Friendly** - Clear UI, helpful tooltips
4. **Production-Ready** - Health checks, logging, error handling
5. **Open Source** - MIT License, community-driven

## 📊 Success Metrics

- [ ] All v2.0 features implemented
- [ ] Performance: < 2s page load
- [ ] Trivy scans: < 30s per image
- [ ] Dark mode: Fully functional
- [ ] Documentation: Complete
- [ ] Community feedback: Positive

---

**Status**: 🟡 In Development
**Target Release**: TBD
**Current Version**: 2.0.0-dev

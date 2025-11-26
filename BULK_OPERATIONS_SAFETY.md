# Bulk Operations Safety Features

## Overview
Bulk operations in Docker Registry UI v2.0 include comprehensive safety features to prevent accidental data loss.

## Safety Features Implemented

### 1. Prominent Danger Warnings
- **Red alert banner** at the top of bulk operations page
- Clear explanation that this is an **expert-only activity**
- Warning about 2+ year old images potentially being base images
- Emphasis that deleted tags **cannot be recovered**
- Notice that system has **no usage history tracking**

### 2. Mandatory Fields
- **"Keep minimum tags" is REQUIRED** when using age-based deletion
- Field is marked with red asterisk and "REQUIRED" label
- Validation prevents operation if age filter is set without keep minimum
- Recommended default: 5 or more tags

### 3. Confirmation Checkbox
- User must check: "I understand this is a dangerous operation"
- Run button is **disabled by default**
- Only enabled after reading and confirming warnings

### 4. Dry Run Mode
- **Enabled by default** (checkbox checked)
- Forces users to preview results before actual deletion
- Clear label: "ALWAYS TEST FIRST"
- Results show exactly what would be deleted

### 5. AWS-Style Operation Summary
Real-time summary panel showing:

**What You Selected:**
- Registry name
- Repository pattern
- Tag pattern
- Age filter (days)
- Keep minimum count
- Mode (Dry Run vs Live Deletion)

**What Will Happen:**
1. Search repositories matching pattern
2. Find tags matching pattern
3. Filter by age (if specified)
4. Protect N most recent tags
5. Preview or delete matching tags
6. Note about garbage collection requirement

**Final Warning (Live Mode):**
- Deleted tags CANNOT be recovered
- Images must be rebuilt and re-pushed
- No knowledge of active deployments

### 6. Input Validation
- Age filter requires positive number
- Keep minimum automatically set to 5 if age filter is used
- Red border on keep minimum field when required
- JavaScript validation before API call
- Backend validation in API endpoint

### 7. Visual Indicators
- **Danger button** (red) instead of primary (blue)
- Warning icon on button
- Color-coded badges (green for dry run, red for live)
- Border highlighting on required fields

## User Workflow

### Safe Workflow (Recommended)
1. Read all warnings carefully
2. Configure repository and tag patterns
3. Set age filter (e.g., 365 days)
4. **Set keep minimum to 5 or more**
5. Leave "Dry run" checked
6. Review operation summary
7. Check confirmation checkbox
8. Click "Run Bulk Operation"
9. **Review dry run results carefully**
10. If results look correct, uncheck "Dry run"
11. Run again for actual deletion
12. Run garbage collection manually

### What Prevents Accidents

| Risk | Prevention |
|------|-----------|
| Deleting all images | Mandatory "keep minimum" field |
| Not understanding impact | Comprehensive warnings and summary |
| Accidental live deletion | Dry run enabled by default |
| Running without review | Confirmation checkbox required |
| Missing garbage collection | Info alert about manual GC requirement |

## Limitations (By Design)

### No Usage History
- System does **NOT track** which images are in use
- Cannot detect if image is deployed in production
- Cannot identify base images used by other images
- User must know their deployment architecture

### Static Rules Only
- Rules based on age, pattern, count only
- No integration with orchestration systems (K8s, Docker Swarm)
- No pull count or last-used metrics
- No dependency analysis

### Manual Garbage Collection
- Deleting tags only removes manifest references
- Actual image layers remain on disk
- User must run GC manually to free space
- See "Cleanup Instructions" menu for commands

## Best Practices

### Before Running Bulk Operations
1. **Document your images**: Know which images are critical
2. **Check deployments**: Verify what's running in production
3. **Test with dry run**: Always preview first
4. **Start conservative**: Use higher keep minimum (10+) initially
5. **One repo at a time**: Don't use wildcard patterns initially

### Recommended Keep Minimum Values
- **Development repos**: 5-10 tags
- **Staging repos**: 10-20 tags
- **Production repos**: 20-50 tags
- **Base images**: 50+ tags or don't use bulk operations

### When NOT to Use Bulk Operations
- Production base images (e.g., company-wide base images)
- Images with unknown usage
- Repositories you don't fully understand
- When you're unsure about deployment dependencies

## Recovery Options

### If You Accidentally Delete Important Tags
1. **Check your CI/CD pipeline**: May have build artifacts
2. **Rebuild from source**: If you have the Dockerfile and code
3. **Restore from backup**: If you backup your registry
4. **Pull from other environments**: Dev/staging may have copies

### Prevention is Key
- **Backup your registry** regularly
- **Use dry run** every time
- **Keep higher minimum** than you think you need
- **Document critical images** before cleanup

## Technical Implementation

### Frontend Validation
```javascript
// Validates keep minimum is set when age filter is used
if (olderThan && keepMin < 1) {
    showAlert('ERROR: Keep minimum tags is REQUIRED');
    return;
}
```

### Backend Validation
```python
# API validates and enforces keep minimum
if older_than_days and keep_min < 1:
    return jsonify({"error": "Keep minimum required"}), 400
```

### Summary Generation
- Real-time updates as user types
- Clear English explanation of what will happen
- Color-coded warnings for dangerous operations
- Step-by-step breakdown of operation logic

## Comparison with Other Tools

### Harbor
- Has usage statistics and vulnerability scanning
- Tracks pull counts and last pull time
- More sophisticated retention policies
- **Trade-off**: Requires database and more resources

### Docker Registry UI v2.0
- No database required (stateless)
- Simple rule-based cleanup
- Comprehensive warnings and dry run
- **Trade-off**: No usage history, user must be careful

## Conclusion

Bulk operations in Docker Registry UI v2.0 are designed with **safety first**:
- Multiple layers of warnings
- Mandatory fields and validation
- Dry run mode by default
- AWS-style operation summary
- Clear documentation of limitations

**Remember**: This is a powerful tool for experts who understand their registry and deployment architecture. When in doubt, don't use bulk operations - delete tags manually instead.

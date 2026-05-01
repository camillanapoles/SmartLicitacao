# Next Command Suggestions

## Purpose

Suggest next commands based on current workflow context using the Workflow Intelligence System (WIS). Helps users navigate workflows efficiently without memorizing command sequences.

AIOX 4.0.4 runtime-first mode adds deterministic next-step recommendation from
execution signals (story/qa/ci/diff) via `workflow-state-manager`.

## Task Definition (AIOX Task Format V1.0)

```yaml
task: next()
agent: "@dev"
responsável: Dex (Developer)
responsavel_type: Agente
atomic_layer: Workflow

elicit: false

inputs:
  - name: story
    type: path
    required: false
    description: Explicit story path for context

  - name: all
    type: flag
    required: false
    default: false
    description: Show all suggestions instead of top 3

  - name: help
    type: flag
    required: false
    default: false
    description: Show usage documentation

outputs:
  - name: suggestions
    type: array
    destino: Console
    persistido: false

  - name: workflow_context
    type: object
    destino: Console
    persistido: false
```

---

## Pre-Conditions

```yaml
pre-conditions:
  - [ ] WIS modules are available
    tipo: pre-condition
    blocker: false
    validação: Check workflow-intelligence module loads
    error_message: "WIS not available. Suggestions may be limited."

  - [ ] Session state exists (optional)
    tipo: pre-condition
    blocker: false
    validação: Check .aiox/session-state.json exists
    error_message: "No session history. Using project context only."

  - [ ] Claims directory accessible (optional)
    tipo: pre-condition
    blocker: false
    validação: Check .aiox/claims/ can be read/written
    error_message: "Cannot access .aiox/claims/. Running without parallel-session claim registry."
```

---

## Implementation Steps

### Step 0: Session Init & Load Claims

Before doing anything else, set up session identity and load the parallel-session claim registry.

```bash
# Derive a stable SESSION_ID for this terminal session
SESSION_ID="$(date +%s)-$(cat /dev/urandom | tr -dc 'a-z0-9' | head -c 4 2>/dev/null || echo 'xxxx')"

# Ensure claims directory exists
mkdir -p .aiox/claims

# Prune stale claims (TTL expired)
# For each .aiox/claims/*.yaml:
#   Parse claimed_at and ttl_seconds
#   If (now - claimed_at) > ttl_seconds → delete file
NOW=$(date -u +%s)
for claim_file in .aiox/claims/*.yaml; do
  [ -f "$claim_file" ] || continue
  claimed_at_iso=$(grep 'claimed_at:' "$claim_file" | awk '{print $2}' | tr -d '"')
  ttl=$(grep 'ttl_seconds:' "$claim_file" | awk '{print $2}')
  claimed_at_epoch=$(date -d "$claimed_at_iso" +%s 2>/dev/null || echo 0)
  if [ $((NOW - claimed_at_epoch)) -gt "${ttl:-1800}" ]; then
    rm -f "$claim_file"
  fi
done

# Load CLAIMED_STORIES: collect story_path from all remaining claim files
CLAIMED_STORIES=()
for claim_file in .aiox/claims/*.yaml; do
  [ -f "$claim_file" ] || continue
  story_path=$(grep 'story_path:' "$claim_file" | awk '{print $2}' | tr -d '"')
  [ -n "$story_path" ] && CLAIMED_STORIES+=("$story_path")
done
```

If `.aiox/claims/` is not accessible, continue without the registry — non-blocking.

---

### Step 1: Check Help Flag
```javascript
if (args.help) {
  displayHelp();
  return;
}
```

### Step 2: Build Context
```javascript
const SuggestionEngine = require('.aiox-core/workflow-intelligence/engine/suggestion-engine');
const engine = new SuggestionEngine();

// Build context from multiple sources
const context = await engine.buildContext({
  storyOverride: args.story,    // Explicit story path (optional)
  autoDetect: true,             // Auto-detect from session/git
  excludeStories: CLAIMED_STORIES, // Stories claimed by other parallel sessions
});
```

### Step 3: Runtime-First Deterministic Recommendation (Preferred)
```javascript
const { WorkflowStateManager } = require('.aiox-core/development/scripts/workflow-state-manager');
const manager = new WorkflowStateManager();

const runtimeNext = manager.getNextActionRecommendation(
  {
    story_status: context.projectState?.storyStatus || 'unknown',
    qa_status: context.projectState?.qaStatus || 'unknown',
    ci_status: context.projectState?.ciStatus || 'unknown',
    has_uncommitted_changes: context.projectState?.hasUncommittedChanges || false,
  },
  { story: args.story || context.storyPath || '' },
);
```

### Step 4: Get WIS Suggestions (Fallback / enrichment)
```javascript
const result = await engine.suggestNext(context);

// result = {
//   workflow: 'story_development',
//   currentState: 'in_development',
//   confidence: 0.92,
//   suggestions: [
//     { command: '*review-qa', args: '${story_path}', description: '...', confidence: 0.95, priority: 1 },
//     ...
//   ]
// }

// Filter out suggestions targeting stories already claimed by other sessions
const extractStoryPath = (args) => {
  // Match anything that looks like a docs/stories/... path in the args string
  const match = String(args || '').match(/(docs\/stories\/[^\s]+\.story\.md)/);
  return match ? match[1] : null;
};

result.suggestions = result.suggestions.filter(suggestion => {
  const storyPathInArgs = extractStoryPath(suggestion.args);
  if (!storyPathInArgs) return true; // Non-story suggestions always pass through
  return !CLAIMED_STORIES.includes(storyPathInArgs);
});

// If all suggestions were filtered, add a notice
if (result.suggestions.length === 0 && CLAIMED_STORIES.length > 0) {
  result.suggestions = [{
    command: '*next --all',
    args: '',
    description: `All available stories are claimed by ${CLAIMED_STORIES.length} parallel session(s). Try *next --all to see claimed items or wait for a session to release.`,
    confidence: 0.5,
    priority: 1,
  }];
}
```

### Step 5: Format Output
```javascript
const formatter = require('.aiox-core/workflow-intelligence/engine/output-formatter');

const runtimeSuggestion = {
  command: runtimeNext.command,
  args: '',
  description: runtimeNext.rationale,
  confidence: runtimeNext.confidence,
  priority: 1,
};
const mergedSuggestions = [runtimeSuggestion, ...(result.suggestions || [])];
const displaySuggestions = args.all ? mergedSuggestions : mergedSuggestions.slice(0, 3);

// Display formatted output
formatter.displaySuggestions({
  workflow: result.workflow || 'runtime_first',
  currentState: runtimeNext.state,
  confidence: runtimeNext.confidence,
  suggestions: displaySuggestions,
  parallelSessionsInfo: CLAIMED_STORIES.length > 0
    ? `🔒 ${CLAIMED_STORIES.length} story(s) in use by other sessions (excluded from suggestions)`
    : null,
});
```

---

### Step 5b: Register Claim

After displaying suggestions, register a claim so parallel sessions know this session is working on a specific story.

```javascript
// Determine which story this session is working on
const ACTIVE_STORY =
  extractStoryPath(displaySuggestions[0]?.args) || // top suggestion has story path
  context.storyPath ||                              // auto-detected current story
  args.story ||                                     // explicitly passed --story
  null;

if (ACTIVE_STORY) {
  // Derive slug: basename without extension, lowercase, non-alphanum → dash
  const storySlug = path.basename(ACTIVE_STORY, '.story.md')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

  const claimContent = [
    `session_id: "${SESSION_ID}"`,
    `story_path: "${ACTIVE_STORY}"`,
    `claimed_at: "${new Date().toISOString()}"`,
    `ttl_seconds: 1800`,
  ].join('\n');

  // Write claim file (overwrite if this session re-runs *next on same story)
  fs.writeFileSync(`.aiox/claims/${storySlug}.yaml`, claimContent + '\n');

  console.log(`🔒 Story claimed for this session: ${ACTIVE_STORY}`);
}
```

**Non-blocking:** If claim write fails (permissions, disk), emit a warning and continue.

---

## Help Text

```
Usage: *next [options]

Suggests next commands based on current workflow context.

Options:
  --story <path>  Explicit story path for context
  --all           Show all suggestions (not just top 3)
  --help          Show this help message

Examples:
  *next                                    # Auto-detect context
  *next --story docs/stories/v4.0.4/sprint-10/story-wis-3.md
  *next --all                              # Show all suggestions

How it works:
  1. Analyzes your recent commands and current agent
  2. Matches to known workflow patterns (story development, epic creation, etc.)
  3. Determines your current state in the workflow
  4. Suggests most likely next commands with confidence scores

Workflow detection uses:
  - Recent command history (last 10 commands)
  - Current active agent
  - Git branch and status
  - Active story (if any)
```

---

## Output Format

### Standard Output
```
🧭 Workflow: story_development
📍 State: in_development (confidence: 92%)

Next steps:
1. `*review-qa docs/stories/v4.0.4/sprint-10/story-wis-3.md` - Run QA review
2. `*run-tests` - Execute test suite manually
3. `*pre-push-quality-gate` - Final quality checks

Type a number to execute, or press Enter to continue manually.
🔒 Story claimed for this session: docs/stories/v4.0.4/sprint-10/story-wis-3.md
```

### Standard Output (with parallel sessions active)
```
🧭 Workflow: story_development
📍 State: in_development (confidence: 92%)
🔒 2 story(s) in use by other sessions (excluded from suggestions)

Next steps:
1. `*review-qa docs/stories/v4.0.4/sprint-11/story-wis-4.md` - Run QA review
2. `*run-tests` - Execute test suite manually
3. `*pre-push-quality-gate` - Final quality checks

Type a number to execute, or press Enter to continue manually.
🔒 Story claimed for this session: docs/stories/v4.0.4/sprint-11/story-wis-4.md
```

### Low Confidence Output
```
🧭 Workflow: unknown
📍 State: uncertain (confidence: 35%)

Possible next steps (uncertain):
1. `*help` - Show available commands
2. `*status` - Check project status

⚠️ Low confidence - context is unclear. Try providing --story flag.
```

### No Workflow Match
```
🧭 Workflow: none detected
📍 State: N/A

Unable to determine workflow from current context.

Try:
  *next --story <path-to-story>
  *help

Recent commands: *develop, *run-tests
Current agent: @dev
```

---

## Post-Conditions

```yaml
post-conditions:
  - [ ] Suggestions displayed within 100ms
    tipo: post-condition
    blocker: false
    validação: Measure execution time

  - [ ] Output is properly formatted
    tipo: post-condition
    blocker: true
    validação: Verify console output matches expected format

  - [ ] Claim written when active story detected
    tipo: post-condition
    blocker: false
    validação: Check .aiox/claims/{story-slug}.yaml exists and has valid YAML
    error_message: "Claim write failed — parallel sessions will not see this session's active story"

  - [ ] Stale claims pruned
    tipo: post-condition
    blocker: false
    validação: No .aiox/claims/*.yaml files with expired TTL remain
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| WIS module not found | Missing dependency | Fallback to generic suggestions |
| Session state corrupt | Invalid JSON | Clear session, show warning |
| Story path invalid | File doesn't exist | Warning, use auto-detect |
| No workflow match | Unknown command pattern | Show "unable to determine" message |

**Error Recovery Strategy:**
```javascript
try {
  const result = await engine.suggestNext(context);
  formatter.displaySuggestions(result);
} catch (error) {
  console.warn(`⚠️ Suggestion engine error: ${error.message}`);
  // Fallback: show generic suggestions
  formatter.displayFallback();
}
```

---

## Performance

```yaml
duration_expected: <100ms (target)
cost_estimated: $0.00 (no API calls)
token_usage: 0 (local processing only)

optimizations:
  - Workflow patterns cached (5-min TTL)
  - Lazy loading of WIS modules
  - Session state read once per call
```

---

## Success Output

```
============================================
 SUGGESTION ENGINE RESULTS
============================================

 Context:
   Agent: @dev
   Last Command: *develop
   Story: docs/stories/v4.0.4/sprint-11/story-wis-3.md
   Branch: feature/wis-3

 Workflow: story_development
 State: in_development
 Confidence: 92%

 Suggestions:
   1. *review-qa (confidence: 95%)
   2. *run-tests (confidence: 80%)
   3. *pre-push-quality-gate (confidence: 75%)

============================================
```

---

## Metadata

```yaml
story: WIS-3
version: 1.1.0
created: 2025-12-25
updated: 2026-05-01
author: "@dev (Dex)"
dependencies:
  modules:
    - workflow-intelligence (from WIS-2)
    - core/session/context-loader
  tasks: []
tags:
  - workflow-intelligence
  - suggestions
  - navigation
  - context-aware
  - parallel-sessions
```

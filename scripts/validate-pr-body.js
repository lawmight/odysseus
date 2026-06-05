#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const checkPrDescription = require('../.github/scripts/check-pr-description.js');
const validatePrDescription = checkPrDescription.validatePrDescription;

const EXPLAIN = {
  '**Summary** is empty or too short — describe what changed and why.': {
    n: 1,
    section: '## Summary',
    fix: 'Write at least 20 characters describing what changed and why (not "fix" or "docs only").',
  },
  '**Linked Issue** — add a reference like `Fixes #NNN`, a bare `#NNN`, or a link to the issue.': {
    n: 2,
    section: '## Linked Issue',
    fix: 'Add Fixes #123, Part of #123, or https://github.com/pewdiepie-archdaemon/odysseus/issues/123 (fork issues are disabled).',
  },
  '**Type of Change** — check at least one box.': {
    n: 3,
    section: '## Type of Change',
    fix: 'Change one `- [ ]` to `- [x]` in the Type of Change section.',
  },
  '**Checklist** — check the duplicate-search box to confirm you searched existing issues and PRs.': {
    n: 4,
    section: '## Checklist',
    fix: 'Check the line: `- [x] I searched` (duplicate-search checkbox).',
  },
  '**How to Test** — explain how a reviewer can verify this change. Numbered steps, the commands you ran, or a short code block all work — give a sentence or two of real detail (not just "tested locally").': {
    n: 5,
    section: '## How to Test',
    fix: 'Add at least ~30 characters of real verification detail (numbered steps, commands run, or a short code block).',
  },
};

function usage() {
  console.error(`Usage: node scripts/validate-pr-body.js [--explain] <pr-body.md>
       node scripts/validate-pr-body.js [--explain] --stdin`);
  process.exit(2);
}

function readBody(argv) {
  let explain = false;
  let stdin = false;
  let file = null;

  for (const arg of argv) {
    if (arg === '--explain') explain = true;
    else if (arg === '--stdin') stdin = true;
    else if (arg.startsWith('-')) {
      console.error(`Unknown option: ${arg}`);
      usage();
    } else file = arg;
  }

  let body;
  if (stdin) body = fs.readFileSync(0, 'utf8');
  else if (file) body = fs.readFileSync(path.resolve(file), 'utf8');
  else usage();

  return { body, explain };
}

function main() {
  const { body, explain } = readBody(process.argv.slice(2));
  const problems = validatePrDescription(body);

  if (problems.length === 0) {
    console.log('PR description: OK');
    process.exit(0);
  }

  console.error(`PR description has ${problems.length} issue(s):`);
  for (const p of problems) {
    const plain = p.replace(/\*\*/g, '');
    console.error(`- ${plain}`);
    if (explain) {
      const info = EXPLAIN[p];
      if (info) {
        console.error(`    Check #${info.n}: ${info.section}`);
        console.error(`    ${info.fix}`);
      }
    }
  }
  console.error('');
  console.error('Fix: bash scripts/scaffold-pr-body.sh --issue NNNN --summary "..." -o pr-body.md');
  console.error('     node scripts/validate-pr-body.js pr-body.md');
  process.exit(1);
}

main();

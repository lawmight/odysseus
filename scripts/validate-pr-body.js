#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const checkPrDescription = require('../.github/scripts/check-pr-description.js');
const validatePrDescription = checkPrDescription.validatePrDescription;

function usage() {
  console.error(`Usage: node scripts/validate-pr-body.js <pr-body.md>
       node scripts/validate-pr-body.js --stdin`);
  process.exit(2);
}

async function main() {
  let body;
  if (process.argv[2] === '--stdin') {
    body = fs.readFileSync(0, 'utf8');
  } else if (process.argv[2]) {
    body = fs.readFileSync(path.resolve(process.argv[2]), 'utf8');
  } else {
    usage();
  }

  const problems = validatePrDescription(body);
  if (problems.length === 0) {
    console.log('PR description: OK');
    process.exit(0);
  }

  console.error('PR description has', problems.length, 'issue(s):');
  for (const p of problems) {
    console.error('-', p.replace(/\*\*/g, ''));
  }
  process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

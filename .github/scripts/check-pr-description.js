// @ts-check
'use strict';

/** @param {string} body */
function stripComments(body) {
  return (body ?? '').replace(/<!--[\s\S]*?-->/g, '').trim();
}

/** @param {string} body @param {string} heading */
function sectionText(body, heading) {
  const m = body.match(new RegExp(`#+\\s+${heading}[\\s\\S]*?(?=\\n#+\\s+|$)`, 'i'));
  return stripComments(m?.[0].replace(new RegExp(`#+\\s+${heading}`, 'i'), '') ?? '');
}

/** @param {string} body @returns {string[]} */
function validatePrDescription(body) {
  const problems = [];

  if (sectionText(body, 'Summary').length < 20) {
    problems.push('**Summary** is empty or too short — describe what changed and why.');
  }

  const linkedSection = sectionText(body, 'Linked Issue');
  const hasIssueRef = /#\d+/.test(linkedSection) || /\/issues\/\d+/.test(linkedSection);
  if (!linkedSection || !hasIssueRef) {
    problems.push('**Linked Issue** — add a reference like `Fixes #NNN`, a bare `#NNN`, or a link to the issue.');
  }

  const typeBlock = body.match(/##\s+Type of Change[\s\S]*?(?=\n##\s|$)/i)?.[0] ?? '';
  if (!/- \[x\]/i.test(typeBlock)) {
    problems.push('**Type of Change** — check at least one box.');
  }

  if (!/- \[x\] I searched/i.test(body)) {
    problems.push('**Checklist** — check the duplicate-search box to confirm you searched existing issues and PRs.');
  }

  const howTo = sectionText(body, 'How to Test');
  if (!howTo || !/\d+\.\s*\S/.test(howTo)) {
    problems.push('**How to Test** — add at least one numbered step a reviewer can follow to verify this works.');
  }

  return problems;
}

/** @param {{ github: import('@octokit/rest').Octokit, context: import('@actions/github').context, core: import('@actions/core') }} */
async function runPrDescriptionCheck({ github, context, core }) {
  const body   = context.payload.pull_request.body || '';
  const prNum  = context.payload.pull_request.number;
  const MARKER = '<!-- pr-description-check-bot -->';
  const owner  = context.repo.owner;
  const repo   = context.repo.repo;

  const problems = validatePrDescription(body);

  // ── Comment ──────────────────────────────────────────────────────────────
  const comments = await github.paginate(github.rest.issues.listComments, {
    owner, repo, issue_number: prNum, per_page: 100,
  });
  const existing = comments.find(c => (c.body ?? '').includes(MARKER));

  if (problems.length === 0) {
    if (existing) {
      await github.rest.issues.deleteComment({ owner, repo, comment_id: existing.id });
    }
  } else {
    const commentBody = [
      MARKER,
      '⚠️ **PR description — action needed**',
      '',
      'The following required sections are missing or incomplete. Please update the PR description to address them:',
      '',
      problems.map(p => `- ${p}`).join('\n'),
      '',
      '---',
      '_This comment is deleted automatically once all sections are complete._',
    ].join('\n');

    if (existing) {
      await github.rest.issues.updateComment({ owner, repo, comment_id: existing.id, body: commentBody });
    } else {
      await github.rest.issues.createComment({ owner, repo, issue_number: prNum, body: commentBody });
    }
  }

  // ── Labels ────────────────────────────────────────────────────────────────
  // These labels are expected to already exist in the repo — managing the
  // repo's label set is the maintainer's job, not this workflow's. We check a
  // label exists before applying it (issues.addLabels would otherwise silently
  // create a missing label) and fail soft — warn and skip — if it's absent.
  async function labelExists(name) {
    try {
      await github.rest.issues.getLabel({ owner, repo, name });
      return true;
    } catch (e) {
      if (e.status === 404) return false;
      throw e;
    }
  }

  async function swapLabel(num, add, remove) {
    if (await labelExists(add)) {
      await github.rest.issues.addLabels({ owner, repo, issue_number: num, labels: [add] });
    } else {
      core.warning(`Label "${add}" does not exist in the repo — skipping. Create it once to enable labelling.`);
    }
    try {
      await github.rest.issues.removeLabel({ owner, repo, issue_number: num, name: remove });
    } catch (e) {
      if (e.status !== 404 && e.status !== 410) throw e;
    }
  }

  if (problems.length === 0) {
    await swapLabel(prNum, 'ready for review', 'needs work');
  } else {
    await swapLabel(prNum, 'needs work', 'ready for review');
    core.setFailed(`PR description has ${problems.length} issue(s) — see bot comment for details.`);
  }
}

module.exports = runPrDescriptionCheck;
module.exports.validatePrDescription = validatePrDescription;

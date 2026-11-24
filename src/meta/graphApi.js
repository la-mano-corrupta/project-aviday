/**
 * Meta Graph API v21.0 Client for Instagram Professional Accounts
 * Handles:
 * - Replying to DMs & Story replies
 * - Replying to Comments
 * - Publishing Posts & Stories
 */

const GRAPH_BASE = 'https://graph.facebook.com/v21.0';

/**
 * Send an Instagram Direct Message (DM)
 */
export async function sendInstagramDM({ env, recipientId, text }) {
  if (!env.META_PAGE_ACCESS_TOKEN || !env.IG_BUSINESS_ACCOUNT_ID) {
    console.log(`[SIMULATED DM -> ${recipientId}]: ${text}`);
    return { simulated: true, recipientId, text };
  }

  const url = `${GRAPH_BASE}/${env.IG_BUSINESS_ACCOUNT_ID}/messages?access_token=${env.META_PAGE_ACCESS_TOKEN}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient: { id: recipientId },
      message: { text }
    })
  });

  const data = await res.json();
  if (!res.ok) {
    console.error('Meta DM Error:', data);
  }
  return data;
}

/**
 * Reply publicly to an Instagram Comment
 */
export async function replyToInstagramComment({ env, commentId, text }) {
  if (!env.META_PAGE_ACCESS_TOKEN) {
    console.log(`[SIMULATED COMMENT REPLY -> ${commentId}]: ${text}`);
    return { simulated: true, commentId, text };
  }

  const url = `${GRAPH_BASE}/${commentId}/replies?access_token=${env.META_PAGE_ACCESS_TOKEN}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text })
  });

  return await res.json();
}

/**
 * Publish an Instagram Story or Feed Image Post
 */
export async function publishInstagramMedia({ env, imageUrl, caption = '', mediaType = 'IMAGE' }) {
  if (!env.META_PAGE_ACCESS_TOKEN || !env.IG_BUSINESS_ACCOUNT_ID) {
    console.log(`[SIMULATED PUBLISH ${mediaType}]: ${imageUrl} | Caption: ${caption}`);
    return { simulated: true, mediaType, imageUrl, caption };
  }

  // Step 1: Create Media Container
  const containerUrl = `${GRAPH_BASE}/${env.IG_BUSINESS_ACCOUNT_ID}/media?access_token=${env.META_PAGE_ACCESS_TOKEN}`;
  const payload = {
    image_url: imageUrl
  };

  if (mediaType === 'STORIES') {
    payload.media_type = 'STORIES';
  } else if (caption) {
    payload.caption = caption;
  }

  const containerRes = await fetch(containerUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const containerData = await containerRes.json();

  if (!containerData.id) {
    throw new Error(`Failed to create media container: ${JSON.stringify(containerData)}`);
  }

  // Step 2: Publish Media Container
  const publishUrl = `${GRAPH_BASE}/${env.IG_BUSINESS_ACCOUNT_ID}/media_publish?access_token=${env.META_PAGE_ACCESS_TOKEN}`;
  const publishRes = await fetch(publishUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ creation_id: containerData.id })
  });

  return await publishRes.json();
}

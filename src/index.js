import {
  buildLomlSystemPrompt,
  buildAdminSystemPrompt,
  buildPublicSystemPrompt
} from './config/about_me.js';
import {
  generateStructuredReply,
  buildFreeGeneratedImageUrl
} from './ai/router.js';
import {
  sendInstagramDM,
  replyToInstagramComment,
  publishInstagramMedia
} from './meta/graphApi.js';

/**
 * Fallback In-Memory Store when running locally without Cloudflare D1 bound yet
 */
const localMemoryStore = {
  ownerState: {
    status_mode: 'online',
    status_message: 'Online and available',
    started_at: null,
    available_at: null,
    last_loml_alert_at: 0,
    extra_notes: ''
  },
  userMemories: new Map(),
  messages: new Map()
};

async function getOwnerState(env) {
  if (env.DB) {
    const row = await env.DB.prepare('SELECT * FROM owner_state WHERE id = 1').first();
    if (row) return row;
  }
  return localMemoryStore.ownerState;
}

async function updateOwnerState(env, updates) {
  const current = await getOwnerState(env);
  const next = { ...current, ...updates };
  if (env.DB) {
    await env.DB.prepare(
      `UPDATE owner_state
       SET status_mode = ?, status_message = ?, started_at = ?, available_at = ?, last_loml_alert_at = ?, extra_notes = ?
       WHERE id = 1`
    )
      .bind(
        next.status_mode,
        next.status_message,
        next.started_at,
        next.available_at,
        next.last_loml_alert_at,
        next.extra_notes
      )
      .run();
  } else {
    Object.assign(localMemoryStore.ownerState, next);
  }
  return next;
}

async function getUserMemory(env, igUserId) {
  if (env.DB) {
    const row = await env.DB.prepare('SELECT * FROM user_memories WHERE ig_user_id = ?')
      .bind(igUserId)
      .first();
    return row?.memory_summary || '';
  }
  return localMemoryStore.userMemories.get(igUserId) || '';
}

async function saveUserMemory(env, igUserId, memorySummary) {
  if (!memorySummary) return;
  if (env.DB) {
    await env.DB.prepare(
      `INSERT INTO user_memories (ig_user_id, memory_summary, updated_at)
       VALUES (?, ?, ?)
       ON CONFLICT(ig_user_id) DO UPDATE SET memory_summary = excluded.memory_summary, updated_at = excluded.updated_at`
    )
      .bind(igUserId, memorySummary, Date.now())
      .run();
  } else {
    localMemoryStore.userMemories.set(igUserId, memorySummary);
  }
}

async function getRecentMessages(env, igUserId, limit = 12) {
  if (env.DB) {
    const { results } = await env.DB.prepare(
      'SELECT role, content FROM messages WHERE ig_user_id = ? ORDER BY created_at DESC LIMIT ?'
    )
      .bind(igUserId, limit)
      .all();
    return (results || []).reverse();
  }
  const list = localMemoryStore.messages.get(igUserId) || [];
  return list.slice(-limit);
}

async function appendMessage(env, igUserId, role, content) {
  if (env.DB) {
    await env.DB.prepare(
      'INSERT INTO messages (ig_user_id, role, content, created_at) VALUES (?, ?, ?, ?)'
    )
      .bind(igUserId, role, content, Date.now())
      .run();
  } else {
    const list = localMemoryStore.messages.get(igUserId) || [];
    list.push({ role, content, created_at: Date.now() });
    localMemoryStore.messages.set(igUserId, list);
  }
}

/**
 * Formats live countdown status (auto-clears if sleep/busy timer expired)
 */
async function formatLiveStatusSummary(env) {
  const state = await getOwnerState(env);
  const now = Date.now();

  if (state.status_mode !== 'online' && state.available_at) {
    if (now >= state.available_at) {
      // Timer finished! Automatically set back to online
      await updateOwnerState(env, {
        status_mode: 'online',
        status_message: 'Online and available',
        started_at: null,
        available_at: null
      });
      return 'Online and available right now.';
    }

    const remainingMs = state.available_at - now;
    const totalMinutes = Math.ceil(remainingMs / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    const timeStr =
      hours > 0
        ? `${hours} hour${hours > 1 ? 's' : ''}${minutes > 0 ? ` and ${minutes} min` : ''}`
        : `${minutes} minutes`;

    return `Currently ${state.status_mode.toUpperCase()} (${state.status_message}). Will be back online in approximately ${timeStr}.`;
  }

  return state.status_message || 'Online and available.';
}

/**
 * Core Handler for Incoming Instagram DMs (3-Tier Identity Router)
 */
export async function handleIncomingDM({ env, senderId, text }) {
  const statusSummary = await formatLiveStatusSummary(env);
  const ownerState = await getOwnerState(env);

  // Support both ADMIN_IG_ID (acc1) and ADMIN_2_IG_ID (acc2), or comma-separated list
  const adminIds = [
    ...(env.ADMIN_IG_ID ? env.ADMIN_IG_ID.split(',').map((s) => s.trim()) : []),
    ...(env.ADMIN_2_IG_ID ? env.ADMIN_2_IG_ID.split(',').map((s) => s.trim()) : [])
  ].filter(Boolean);

  // =========================================================================
  // TIER 1: VIP ACCOUNT — HIGHEST PRIORITY
  // =========================================================================
  if (env.LOML_IG_ID && senderId === env.LOML_IG_ID) {
    // 1. Send silent heads-up to Admin accounts (NO message content forwarded, 15-min cooldown)
    const now = Date.now();
    if (adminIds.length > 0 && now - (ownerState.last_loml_alert_at || 0) > 15 * 60 * 1000) {
      await updateOwnerState(env, { last_loml_alert_at: now });
      for (const adminId of adminIds) {
        await sendInstagramDM({
          env,
          recipientId: adminId,
          text: `❤️ Your ${env.VIP_NAME || 'VIP'} just texted!`
        });
      }
    }

    // 2. Load VIP memory & recent chat
    const userMemory = await getUserMemory(env, senderId);
    await appendMessage(env, senderId, 'user', text);
    const history = await getRecentMessages(env, senderId);

    const systemPrompt = buildLomlSystemPrompt({
      statusSummary,
      userMemory,
      ownerName: env.OWNER_NAME || undefined,
      agentName: env.AGENT_NAME || undefined,
      vipName: env.VIP_NAME || undefined
    });
    const aiResult = await generateStructuredReply({
      env,
      systemPrompt,
      messages: history,
      isVipLoml: true
    });

    const replyText = aiResult.reply || 'Hey! So good to hear from you ❤️';
    await appendMessage(env, senderId, 'assistant', replyText);
    if (aiResult.updated_memory) {
      await saveUserMemory(env, senderId, aiResult.updated_memory);
    }

    await sendInstagramDM({ env, recipientId: senderId, text: replyText });
    return { tier: 'VIP_LOML', reply: replyText };
  }

  // =========================================================================
  // TIER 2: ADMIN CONTROL CENTER ACCOUNTS (acc1 & acc2)
  // =========================================================================
  if (adminIds.includes(senderId)) {
    await appendMessage(env, senderId, 'user', text);
    const history = await getRecentMessages(env, senderId, 6);
    const systemPrompt = buildAdminSystemPrompt({
      statusSummary,
      extraNotes: ownerState.extra_notes,
      ownerName: env.OWNER_NAME || undefined,
      agentName: env.AGENT_NAME || undefined
    });

    const cmd = await generateStructuredReply({
      env,
      systemPrompt,
      messages: history
    });

    let replyText = cmd.reply || 'Command executed, Boss.';

    if (cmd.action === 'set_status') {
      const durationHours = Number(cmd.duration_hours) || 8;
      const now = Date.now();
      const availableAt = now + durationHours * 3600 * 1000;
      await updateOwnerState(env, {
        status_mode: cmd.status_mode || 'sleeping',
        status_message: cmd.status_message || 'Sleeping',
        started_at: now,
        available_at: availableAt
      });
    } else if (cmd.action === 'clear_status') {
      await updateOwnerState(env, {
        status_mode: 'online',
        status_message: 'Online and available',
        started_at: null,
        available_at: null
      });
    } else if (cmd.action === 'add_note' && cmd.note_to_add) {
      const updatedNotes = [ownerState.extra_notes, `- ${cmd.note_to_add}`]
        .filter(Boolean)
        .join('\n');
      await updateOwnerState(env, { extra_notes: updatedNotes });
    } else if (cmd.action === 'publish_media' && cmd.image_prompt) {
      const imageUrl = buildFreeGeneratedImageUrl(cmd.image_prompt);
      await publishInstagramMedia({
        env,
        imageUrl,
        caption: cmd.caption || '',
        mediaType: cmd.media_type || 'STORIES'
      });
    }

    await appendMessage(env, senderId, 'assistant', replyText);
    await sendInstagramDM({ env, recipientId: senderId, text: replyText });
    return { tier: 'ADMIN_CONTROL_CENTER', action: cmd.action, reply: replyText };
  }

  // =========================================================================
  // TIER 3: PUBLIC MODE (Friends, Followers, Strangers)
  // =========================================================================
  const userMemory = await getUserMemory(env, senderId);
  await appendMessage(env, senderId, 'user', text);
  const history = await getRecentMessages(env, senderId);

  const systemPrompt = buildPublicSystemPrompt({
    statusSummary,
    userMemory,
    extraNotes: ownerState.extra_notes,
    ownerName: env.OWNER_NAME || undefined,
    agentName: env.AGENT_NAME || undefined,
    vipName: env.VIP_NAME || undefined
  });

  const aiResult = await generateStructuredReply({
    env,
    systemPrompt,
    messages: history
  });

  const replyText = aiResult.reply || `Hey! ${env.OWNER_NAME || 'the owner'}'s agent here — I'll pass your message along!`;
  await appendMessage(env, senderId, 'assistant', replyText);
  if (aiResult.updated_memory) {
    await saveUserMemory(env, senderId, aiResult.updated_memory);
  }

  await sendInstagramDM({ env, recipientId: senderId, text: replyText });
  return { tier: 'PUBLIC', reply: replyText, updatedMemory: aiResult.updated_memory };
}

/**
 * Cloudflare Worker Entrypoint (24/7 Serverless Endpoint)
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Health check endpoint
    if (url.pathname === '/' && request.method === 'GET') {
      const statusSummary = await formatLiveStatusSummary(env);
      return Response.json({
        ok: true,
        agent: `${env.AGENT_NAME || 'Personal Instagram Agent'} (24/7)`,
        live_status: statusSummary
      });
    }

    // 2. Meta Webhook Verification (GET /webhook)
    if (url.pathname === '/webhook' && request.method === 'GET') {
      const mode = url.searchParams.get('hub.mode');
      const token = url.searchParams.get('hub.verify_token');
      const challenge = url.searchParams.get('hub.challenge');

      if (mode === 'subscribe' && Boolean(env.META_VERIFY_TOKEN) && token === env.META_VERIFY_TOKEN) {
        return new Response(challenge, { status: 200 });
      }
      return new Response('Forbidden', { status: 403 });
    }

    // 3. Meta Webhook Events (POST /webhook)
    if (url.pathname === '/webhook' && request.method === 'POST') {
      const body = await request.json();

      const processEvents = async () => {
        const tasks = [];
        for (const entry of body.entry || []) {
          // A. Handle DMs & Story Replies in parallel (simultaneous multi-user chats)
          for (const event of entry.messaging || []) {
            if (event.message?.is_echo) continue; // Ignore bot's own outgoing messages
            const senderId = event.sender?.id;
            const text = event.message?.text;
            if (senderId && text) {
              tasks.push(handleIncomingDM({ env, senderId, text }));
            }
          }

          // B. Handle Post/Reel Comments in parallel
          for (const change of entry.changes || []) {
            if (change.field === 'comments' && change.value?.text && change.value?.id) {
              const commentId = change.value.id;
              const commenterId = change.value.from?.id || 'commenter';
              if (commenterId === env.IG_BUSINESS_ACCOUNT_ID) continue;

              tasks.push(
                (async () => {
                  const statusSummary = await formatLiveStatusSummary(env);
                  const systemPrompt = buildPublicSystemPrompt({
                    statusSummary,
                    userMemory: await getUserMemory(env, commenterId),
                    extraNotes: (await getOwnerState(env)).extra_notes,
                    ownerName: env.OWNER_NAME || undefined,
                    agentName: env.AGENT_NAME || undefined,
                    vipName: env.VIP_NAME || undefined
                  });

                  const aiResult = await generateStructuredReply({
                    env,
                    systemPrompt,
                    messages: [{ role: 'user', content: `[Instagram Comment]: ${change.value.text}` }]
                  });

                  if (aiResult.reply) {
                    await replyToInstagramComment({ env, commentId, text: aiResult.reply });
                  }
                })()
              );
            }
          }
        }
        await Promise.allSettled(tasks);
      };

      if (ctx?.waitUntil) {
        ctx.waitUntil(processEvents());
      } else {
        await processEvents();
      }

      return new Response('EVENT_RECEIVED', { status: 200 });
    }

    return new Response('Not Found', { status: 404 });
  }
};

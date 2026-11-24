/**
 * Meta Permanent (Never-Expiring) Page & Instagram Access Token Extractor
 *
 * Supports TWO modes:
 * Mode 1 (Easiest - 1 argument): Pass the 2-Month (60-day) User Token you got from "Extend Access Token":
 *   node make-permanent-token.mjs <YOUR_2_MONTH_TOKEN>
 *
 * Mode 2 (3 arguments): Pass App ID + App Secret + 1-Hour Short-Lived Token:
 *   node make-permanent-token.mjs <APP_ID> <APP_SECRET> <SHORT_LIVED_TOKEN>
 */

import fs from 'node:fs';
import path from 'node:path';

const GRAPH_BASE = 'https://graph.facebook.com/v21.0';

async function fetchPermanentPageTokenFromLongUserToken(longLivedUserToken) {
  console.log('🔍 Fetching your Facebook Pages & Linked Instagram Account using your 2-Month Token...');

  const pagesUrl = `${GRAPH_BASE}/me/accounts?fields=id,name,access_token,instagram_business_account{id,username,name}&access_token=${encodeURIComponent(longLivedUserToken.trim())}`;
  const pagesRes = await fetch(pagesUrl);
  const pagesData = await pagesRes.json();

  if (pagesData.error) {
    throw new Error(`Meta API Error: ${pagesData.error.message}`);
  }

  if (!pagesData.data || pagesData.data.length === 0) {
    // Let's also check what permissions this token currently has so we can tell the user clearly
    const permRes = await fetch(`${GRAPH_BASE}/me/permissions?access_token=${encodeURIComponent(longLivedUserToken.trim())}`);
    const permData = await permRes.json();
    throw new Error(
      `No Facebook Pages returned! This happens if 'pages_show_list' or your Page wasn't selected when generating the token.\nCurrent token permissions: ${JSON.stringify(permData.data || permData)}`
    );
  }

  const linkedPage =
    pagesData.data.find((p) => p.instagram_business_account?.id) || pagesData.data[0];

  const permanentPageToken = linkedPage.access_token;
  const igBusinessId = linkedPage.instagram_business_account?.id || '';
  const igUsername = linkedPage.instagram_business_account?.username || '';

  console.log('\n============================================================');
  console.log('✅ SUCCESS! PERMANENT (NEVER-EXPIRING) TOKEN GENERATED!');
  console.log('============================================================');
  console.log(`📄 Facebook Page:           ${linkedPage.name} (ID: ${linkedPage.id})`);
  console.log(`📸 Linked Instagram:        @${igUsername || 'Not detected (add instagram_basic permission)'}`);
  console.log(`🆔 IG_BUSINESS_ACCOUNT_ID:  ${igBusinessId || 'Missing - add instagram_basic permission'}`);
  console.log(`🔑 PERMANENT PAGE TOKEN:    ${permanentPageToken.slice(0, 20)}...${permanentPageToken.slice(-10)}`);
  console.log('============================================================\n');

  // Automatically save to .dev.vars
  const devVarsPath = path.join(process.cwd(), '.dev.vars');
  let existing = '';
  if (fs.existsSync(devVarsPath)) {
    existing = fs.readFileSync(devVarsPath, 'utf8');
  }

  const envLines = [
    `META_PAGE_ACCESS_TOKEN="${permanentPageToken}"`,
    `IG_BUSINESS_ACCOUNT_ID="${igBusinessId}"`,
    `META_VERIFY_TOKEN="${process.env.META_VERIFY_TOKEN || 'CHANGE_ME_VERIFY_TOKEN'}"`
  ];

  fs.writeFileSync(devVarsPath, envLines.join('\n') + '\n' + existing, 'utf8');
  console.log(`💾 Automatically saved META_PAGE_ACCESS_TOKEN and IG_BUSINESS_ACCOUNT_ID to ${devVarsPath}!`);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 1) {
    await fetchPermanentPageTokenFromLongUserToken(args[0]);
    return;
  }

  if (args.length === 3) {
    const [appId, appSecret, shortLivedUserToken] = args;
    console.log('1️⃣ Exchanging 1-hour token for 2-Month User Token...');
    const exchangeUrl = new URL(`${GRAPH_BASE}/oauth/access_token`);
    exchangeUrl.searchParams.set('grant_type', 'fb_exchange_token');
    exchangeUrl.searchParams.set('client_id', appId);
    exchangeUrl.searchParams.set('client_secret', appSecret);
    exchangeUrl.searchParams.set('fb_exchange_token', shortLivedUserToken);

    const longUserRes = await fetch(exchangeUrl);
    const longUserData = await longUserRes.json();
    if (!longUserData.access_token) {
      throw new Error(`Failed to exchange token: ${JSON.stringify(longUserData)}`);
    }
    await fetchPermanentPageTokenFromLongUserToken(longUserData.access_token);
    return;
  }

  console.log('Usage:\n  node make-permanent-token.mjs <YOUR_2_MONTH_TOKEN>');
}

main().catch((err) => {
  console.error('\n❌ Error:', err.message);
  process.exit(1);
});

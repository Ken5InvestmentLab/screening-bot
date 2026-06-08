// index.js — v8（ライブ実績自動更新 + ボラタグ実績 + v13スコアリング対応）
// 主な変更:
// ・/help のバックテスト実績をハードコード → ライブ自動計算に切替
// ・起動時 + 24時間ごとに全シグナルを再集計
// ・スコア別・ボラタグ別の実績を自動表示
// ・最終更新日時を表示

const { Client, GatewayIntentBits, EmbedBuilder } = require('discord.js');
const fs = require('fs');
const https = require('https');
const path = require('path');
const config = require('./config');
const { fetchOHLCVData, fetchRecentBottomSymbols, fetchRecentBottomSignals, fetchAllBottomSignals, fetchPremiumReasonsByAlertIds } = require('./sheets');
const { screenSymbol } = require('./screener');

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.DirectMessages, GatewayIntentBits.GuildMembers],
  partials: ['CHANNEL']
});

const scanningUsers = new Set();
const COLOR      = 0x00b4d8;
const COLOR_WARN = 0xf5a623;
const DISCLAIMER = '⚠️ これは情報提供ツールであり、投資助言ではありません。';
const SNIPER_LOGIC_PATH = path.join(__dirname, 'current_logic_sniper.json');
const PREMIUM_SCAN_BUTTON_PREFIX = 'premium_scan:';
const LOGIC_UPDATE_TARGETS = [
  { name: 'すべての更新候補', value: 'all' },
  { name: 'Stable', value: 'stable' },
  { name: 'Sniper', value: 'sniper' },
  { name: 'Mega すべて', value: 'mega' },
  { name: 'Mega5 短期リバウンド', value: 'mega5_rebound' },
  { name: 'Mega40 深押し反転', value: 'mega40_deep_reversal' },
  { name: 'Mega40 下ヒゲ回復', value: 'mega40_wick_recovery' },
];

function logicUpdateTargetChoices(focused) {
  const q = String(focused || '').toLowerCase();
  return LOGIC_UPDATE_TARGETS
    .filter(item => !q || item.name.toLowerCase().includes(q) || item.value.toLowerCase().includes(q))
    .slice(0, 25);
}

// ============================================================
// ライブ実績キャッシュ
// ============================================================
let statsCache = null;
const sniperLogic = loadSniperLogic();

function loadSniperLogic() {
  try {
    const raw = fs.readFileSync(SNIPER_LOGIC_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    return {
      method: parsed.method ?? 'sniper',
      label: parsed.label ?? 'Sniper',
      description: parsed.description ?? '少数精鋭・高勝率狙いの正式モード',
      conditions: Array.isArray(parsed.conditions) ? parsed.conditions : [],
      updated_at: parsed.updated_at ?? null,
      thresholds: parsed.thresholds ?? {},
      backtest: parsed.backtest ?? null,
    };
  } catch (err) {
    console.warn('[sniper] current_logic_sniper.json の読み込みに失敗:', err.message);
    return {
      method: 'sniper',
      label: 'Sniper',
      description: '少数精鋭・高勝率狙いの正式モード',
      conditions: [],
      updated_at: null,
      thresholds: {},
      backtest: null,
    };
  }
}

function toDateKey(value) {
  if (!value) return null;
  return String(value).replace(/\//g, '-').slice(0, 10);
}

async function refreshStats() {
  try {
    console.log('[stats] 実績データ集計開始...');
    const [ohlcvMap, allSignals] = await Promise.all([
      fetchOHLCVData(),
      fetchAllBottomSignals(0),  // 全期間
    ]);

    // 全シグナル点灯地点を対象にする（バックテストと同じ母集団）
    const entries = [];
    const sniperEntries = [];
    const sniperReleaseDate = toDateKey(sniperLogic.updated_at);
    for (const sig of allSignals) {
      if (sig.perf5bd === null || sig.perf5bd === undefined) continue;
      const data = ohlcvMap.get(sig.symbol);
      if (!data) continue;

      const r = screenSymbol(sig.symbol, data, sig.date, sig.entry, sig.eval5bd, sig.perf5bd);
      if (!r) continue;

      entries.push({
        score:  r.score,
        atrPct: r.atrPct,
        perf:   sig.perf5bd,
      });

      const _sniperMax = sniperLogic.conditions.length || 6;
      if (
        sniperReleaseDate &&
        toDateKey(sig.date) >= sniperReleaseDate &&
        r.sniperEnabled &&
        r.sniperScore === _sniperMax
      ) {
        sniperEntries.push({ perf: sig.perf5bd });
      }
    }

    // ── スコア別集計 ──
    function calcTierStats(items) {
      if (items.length === 0) return { n: 0, wr: 0, avg: 0, pf: 0 };
      const wins   = items.filter(e => e.perf > 0);
      const losses = items.filter(e => e.perf < 0);
      const wr     = (wins.length / items.length * 100);
      const avg    = items.reduce((s, e) => s + e.perf, 0) / items.length;
      const gainSum = wins.reduce((s, e) => s + e.perf, 0);
      const lossSum = Math.abs(losses.reduce((s, e) => s + e.perf, 0));
      const pf     = lossSum > 0 ? gainSum / lossSum : 999;
      return { n: items.length, wr: +wr.toFixed(1), avg: +avg.toFixed(2), pf: +pf.toFixed(2) };
    }

    const star6      = calcTierStats(entries.filter(e => e.score === 6));
    const star5      = calcTierStats(entries.filter(e => e.score === 5));
    const star4      = calcTierStats(entries.filter(e => e.score === 4));
    const all        = calcTierStats(entries);
    const sniperLive = calcTierStats(sniperEntries);

    // ── タイムスタンプ（JST）──
    const now = new Date();
    const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
    const timestamp = `${jst.getUTCFullYear()}/${String(jst.getUTCMonth() + 1).padStart(2, '0')}/${String(jst.getUTCDate()).padStart(2, '0')} ${String(jst.getUTCHours()).padStart(2, '0')}:${String(jst.getUTCMinutes()).padStart(2, '0')} JST`;

    statsCache = {
      total: all.n,
      star6, star5, star4, all,
      sniperLive,
      updatedAt: timestamp,
    };

    console.log(`[stats] 集計完了: ${all.n}件確定 (★6=${star6.n}, ★5=${star5.n}, ★4=${star4.n}, Sniper=${sniperLive.n})`);
  } catch (err) {
    console.error('[stats] 集計エラー:', err.message);
    // エラー時はキャッシュを消さない（前回の値を維持）
  }
}

// ============================================================
// ユーティリティ
// ============================================================
function formatPrice(price) {
  const rounded = roundDisplayPrice(price);
  if (rounded == null) return "-";
  return rounded % 1 === 0 ? String(Math.round(rounded)) : rounded.toFixed(1);
}

function roundDisplayPrice(price) {
  if (price == null || isNaN(price)) return null;
  return Math.round(Number(price) * 10) / 10;
}

function formatDisplayChange(entryPrice, targetPrice, fallbackChange = '0.00') {
  const entry = roundDisplayPrice(entryPrice);
  const target = roundDisplayPrice(targetPrice);
  if (entry !== null && entry > 0 && target !== null) {
    return ((target / entry - 1) * 100).toFixed(2);
  }
  if (fallbackChange !== null && fallbackChange !== undefined && !isNaN(fallbackChange)) {
    return Number(fallbackChange).toFixed(2);
  }
  return '0.00';
}

function getVolTag(atrPct) {
  if (atrPct == null || isNaN(atrPct)) return '';
  if (atrPct < 3.0) return ' 🟢LOW';
  if (atrPct < 6.0) return ' 🟡MID';
  return ' 🔴HIGH';
}

// 1024文字制限対応: Markdownリンク [text](url) のテキスト部分だけ短縮する
function truncatePremiumReason(reason, maxLen) {
  if (reason.length <= maxLen) return reason;
  const match = reason.match(/^\[(.+)\]\((.+)\)$/s);
  if (match) {
    const url = match[2];
    const suffix = `...](${url})`;
    const available = maxLen - 1 - suffix.length; // 1 for '['
    if (available > 0) return `[${match[1].slice(0, available)}${suffix}`;
  }
  return reason.slice(0, maxLen - 3) + '...';
}

function sortResults(results) {
  return results.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    const aPerf = a.futureDiff !== null ? parseFloat(a.futureDiff) : 0.005;
    const bPerf = b.futureDiff !== null ? parseFloat(b.futureDiff) : 0.005;
    if (bPerf !== aPerf) return bPerf - aPerf;
    const aChange = parseFloat(a.change);
    const bChange = parseFloat(b.change);
    if (bChange !== aChange) return bChange - aChange;
    return String(a.symbol).localeCompare(String(b.symbol));
  });
}

// ============================================================
// DM送信
// ============================================================
async function sendResultDMs(user, results, headerEmbed) {
  await user.send({ embeds: [headerEmbed] });

  const CHUNK = 5;
  for (let i = 0; i < results.length; i += CHUNK) {
    const chunk = results.slice(i, i + CHUNK);
    const isLast = i + CHUNK >= results.length;
    const embed  = new EmbedBuilder().setColor(COLOR);

    for (let r of chunk) {
      const tvUrl  = `https://jp.tradingview.com/chart/?symbol=TSE:${r.symbol}`;
      const volTag = getVolTag(r.atrPct);
      r = {
        ...r,
        futureDiff: r.futurePrice != null
          ? formatDisplayChange(r.signalPrice, r.futurePrice, r.futureDiff)
          : r.futureDiff,
        change: r.latestClose != null
          ? formatDisplayChange(r.signalPrice, r.latestClose, r.change)
          : r.change,
      };

      let val;
      if (r.hideScore) {
        // Sniperモード: ★表示なし
        val = `🔫 **Sniperモード検出**${volTag}\n`;
      } else {
        const maxScore = r.maxScore || 6;
        const scoreBar = '★'.repeat(r.score) + '☆'.repeat(Math.max(0, maxScore - r.score));
        // Stable/Aggressiveで Sniper条件も満たす銘柄にはタグを付加
        const sniperBadge = r.sniperTag ? ' 🎯' : '';
        val = `${scoreBar} **${r.score}/${maxScore}点**${volTag}${sniperBadge}\n`;
      }
      val += `点灯日: ${r.signalDate}　エントリー: **${formatPrice(r.signalPrice)}円**\n`;
      if (r.futurePrice) {
        const prefix = parseFloat(r.futureDiff) >= 0 ? '+' : '';
        val += `5日後: ${formatPrice(r.futurePrice)}円 (${prefix}${r.futureDiff}%)\n`;
      } else {
        val += `5日後: 未確定\n`;
      }
      if (r.latestClose != null) {
        const chPrefix = parseFloat(r.change) >= 0 ? '+' : '';
        val += `現在: ${formatPrice(r.latestClose)}円 (${chPrefix}${r.change}%)\n`;
      }
      if (r.marketPhase) {
        val += `${r.marketPhase}\n`;
      }
      if (r.filters && r.filters.length > 0) {
        val += `通過: ${r.filters.join(' / ')}\n`;
      } else {
        val += `通過: なし\n`;
      }
      val += `[📊 チャート](${tvUrl})`;
      if (r.premiumReason) {
        const prefix = '\n🏦 ';
        const available = 1024 - val.length - prefix.length;
        if (available > 10) val += prefix + truncatePremiumReason(r.premiumReason, available);
      }

      embed.addFields({ name: `${r.symbol}　${r.name ?? ''}`, value: val, inline: false });
    }

    if (isLast) embed.setFooter({ text: DISCLAIMER });
    await user.send({ embeds: [embed] });
  }
}

async function sendUnanalyzed(user, unanalyzed) {
  if (unanalyzed.length === 0) return;

  const CHUNK = 20;
  for (let i = 0; i < unanalyzed.length; i += CHUNK) {
    const chunk  = unanalyzed.slice(i, i + CHUNK);
    const isFirst = i === 0;
    const isLast  = i + CHUNK >= unanalyzed.length;

    const embed = new EmbedBuilder()
      .setColor(COLOR_WARN)
      .setTitle(isFirst ? `📋 OHLCVデータ未収集 銘柄一覧（${unanalyzed.length}件）` : '📋 続き')

    if (isFirst) {
      embed.setDescription(
        'これらの銘柄は現在データが不足しているためスコアを計算できません。\n' +
        'データは毎日18:30〜19:30頃に自動更新されるため、次回の更新後に分析対象となります。'
      );
    }

    let text = '';
    for (const u of chunk) {
      const perfStr = u.perf_5bd !== null ? ` | 5日後: ${u.perf_5bd >= 0 ? '+' : ''}${u.perf_5bd}%` : '';
      text += `**${u.symbol}** ${u.name}${perfStr}\n`;
    }
    embed.addFields({ name: '\u200b', value: text });

    if (isLast) embed.setFooter({ text: DISCLAIMER });
    await user.send({ embeds: [embed] });
  }
}

// ============================================================
// ロール制限チェック
// ============================================================
async function checkRole(interaction) {
  const GUILD_ID       = config.GUILD_ID;
  const ALLOWED_ROLE_ID = config.ALLOWED_ROLE_ID;
  if (!GUILD_ID || !ALLOWED_ROLE_ID) return true;

  let member = interaction.member;
  if (!member) {
    try {
      const guild = await client.guilds.fetch(GUILD_ID);
      member = await guild.members.fetch(interaction.user.id);
    } catch { member = null; }
  }
  return member?.roles?.cache?.has(ALLOWED_ROLE_ID) ?? false;
}

// ============================================================
// スキャン実行
// ============================================================
async function runScan(interaction) {
  const user = interaction.user;

  if (!(await checkRole(interaction))) {
    return interaction.reply({
      content: '❌ このコマンドを使用するには専用ロールが必要です。\nサービスの詳細はサーバーをご確認ください。',
      ephemeral: true,
    });
  }

  if (scanningUsers.has(user.id)) {
    return interaction.reply({ content: '⚙️ 現在実行中です。少しお待ちください。', ephemeral: true });
  }

  const modeKey    = interaction.options.getString('mode');
  const rangeInput = interaction.options.getString('range');

  if (modeKey === 'code') {
    return runCodeSearch(interaction, user, rangeInput);
  }

  const isSniperMode   = modeKey === 'sniper';
  // Sniper閾値はJSONの条件数から動的に取得（5条件→5点満点、6条件→6点満点）
  const sniperMaxScore = sniperLogic.conditions.length || 6;
  const modeMinScore   = isSniperMode ? sniperMaxScore : modeKey === 'aggressive' ? 4 : 5;
  const modeLabel = isSniperMode
    ? '🔫 Sniper（勝率重視）'
    : modeKey === 'aggressive'
      ? '⚡ Aggressive（4点以上）'
      : '🎯 Stable（5点以上）';

  await interaction.reply({ content: '🚀 解析を開始します。DMに結果をお送りします...', ephemeral: true });

  let prog;
  try {
    prog = await user.send('⏳ データ読み込み中...');
  } catch {
    return interaction.editReply({
      content: '❌ DMを受信できません。\nDiscord設定 → プライバシー・安全 → 「サーバーのメンバーからのDMを許可」をONにしてください。',
      ephemeral: true,
    });
  }

  scanningUsers.add(user.id);

  try {
    const isYesterday  = rangeInput === 'yesterday';
    const yesterday    = (() => { const d = new Date(); d.setDate(d.getDate() - 1); return d.toISOString().slice(0, 10); })();
    const isDate       = /^\d{4}-\d{2}-\d{2}$/.test(rangeInput);
    const specificDate = isYesterday ? yesterday : isDate ? rangeInput : null;
    const rangeDays    = (isYesterday || isDate) ? null : parseInt(rangeInput);

    const [ohlcvMap, signals] = await Promise.all([
      fetchOHLCVData(),
      fetchRecentBottomSignals(specificDate, rangeDays),
    ]);

    await prog.edit('🔍 フィルタリング中...');

    const scored    = [];
    const unanalyzed = [];

    for (const sig of signals) {
      const data = ohlcvMap.get(sig.symbol);
      if (!data) {
        unanalyzed.push({ symbol: sig.symbol, name: sig.name ?? sig.symbol, date: sig.date, perf_5bd: sig.perf5bd ?? null });
        continue;
      }
      const r = screenSymbol(sig.symbol, data, sig.date, sig.entry, sig.eval5bd, sig.perf5bd);
      if (!r) continue;
      const scanResult = isSniperMode
        ? {
            ...r,
            score: r.sniperScore,
            maxScore: sniperMaxScore,
            filters: r.sniperFilters,
            hideScore: true,
          }
        : {
            ...r,
            // Stable/Aggressive表示時: Sniperにも引っかかっていたらタグを付与
            sniperTag: r.sniperEnabled && r.sniperScore === sniperMaxScore,
          };

      if (isSniperMode && !r.sniperEnabled) continue;

      scanResult.name = sig.name;
      scanResult.alertId = sig.alertId;
      if (scanResult.score >= modeMinScore) scored.push(scanResult);
    }

    // Premium理由を取得（失敗してもスキャン続行）
    let premiumReasonMap = new Map();
    try {
      if (config.PREMIUM_SPREADSHEET_ID) {
        premiumReasonMap = await fetchPremiumReasonsByAlertIds(signals);
      }
    } catch (err) {
      console.warn('[scan] Premium理由取得エラー（スキップ）:', err.message);
    }
    for (const r of scored) {
      if (r.alertId && premiumReasonMap.has(r.alertId)) {
        r.premiumReason = premiumReasonMap.get(r.alertId);
      }
    }

    sortResults(scored);
    unanalyzed.sort((a, b) => (b.perf_5bd ?? -999) - (a.perf_5bd ?? -999));

    const rangeText = isYesterday          ? '前日'
      : isDate                             ? rangeInput
      : rangeInput === '1'                 ? '当日'
      : rangeInput === '0'                 ? '全期間'
      : `直近${rangeInput}日`;

    await prog.delete().catch(() => {});

    const headerEmbed = new EmbedBuilder()
      .setTitle('🔍 BOTTOMシグナル スクリーニング結果')
      .setDescription(
        `モード: **${modeLabel}**\n` +
        `期間: ${rangeText}\n` +
        `スキャン対象: **${signals.length}件**\n` +
        `スコア該当: **${scored.length}件**　データなし: **${unanalyzed.length}件**`
      )
      .setColor(COLOR)
      .setTimestamp();

    if (scored.length === 0 && unanalyzed.length === 0) {
      headerEmbed.setDescription(
        isSniperMode
          ? `モード: **${modeLabel}**\n期間: ${rangeText}\n該当銘柄: **0件**\n\nSniper は条件が厳しいため、Stableモードもあわせてお試しください。`
          : `モード: **${modeLabel}**\n期間: ${rangeText}\n該当銘柄: **0件**\n\n期間を広げるか、Aggressiveモードをお試しください。`
      );
      headerEmbed.setFooter({ text: DISCLAIMER });
      await user.send({ embeds: [headerEmbed] });
    } else if (scored.length === 0) {
      headerEmbed.setDescription(
        isSniperMode
          ? `モード: **${modeLabel}**\n期間: ${rangeText}\nスコア該当: **0銘柄**（条件未達）\nOHLCVデータなし: **${unanalyzed.length}銘柄**（下記参照）\n\nSniper は条件が厳しいため、Stableモードもあわせてお試しください。`
          : `モード: **${modeLabel}**\n期間: ${rangeText}\nスコア該当: **0銘柄**（条件未達）\nOHLCVデータなし: **${unanalyzed.length}銘柄**（下記参照）\n\nAggressiveモードをお試しください。`
      );
      await user.send({ embeds: [headerEmbed] });
      await sendUnanalyzed(user, unanalyzed);
    } else {
      await sendResultDMs(user, scored, headerEmbed);
      if (unanalyzed.length > 0) await sendUnanalyzed(user, unanalyzed);
    }

    await interaction.editReply({
      content: `✅ 完了！DM（スコア該当${scored.length}件 + 未分析${unanalyzed.length}件）を確認してください。`,
      ephemeral: true,
    });
  } catch (err) {
    console.error('[scan] エラー:', err);
    await interaction.editReply({ content: `❌ エラーが発生しました: ${err.message}`, ephemeral: true });
    await user.send(`❌ エラー: ${err.message}`).catch(() => {});
  } finally {
    scanningUsers.delete(user.id);
  }
}

// ============================================================
// コード検索実行
// ============================================================
async function runCodeSearch(interaction, user, codeInput) {
  const symbolCode = String(codeInput).trim().toUpperCase();

  if (!/^\d{3,4}[A-Z]?$/.test(symbolCode)) {
    return interaction.reply({
      content: '❌ 証券コードは4桁の数字または3桁+英字（例: 6731, 428A）で入力してください。',
      ephemeral: true,
    });
  }

  await interaction.reply({ content: `🔍 ${symbolCode} のシグナル履歴を検索中...`, ephemeral: true });

  let prog;
  try {
    prog = await user.send(`⏳ ${symbolCode} を検索中...`);
  } catch {
    return interaction.editReply({
      content: '❌ DMを受信できません。\nDiscord設定 → プライバシー・安全 → 「サーバーのメンバーからのDMを許可」をONにしてください。',
      ephemeral: true,
    });
  }

  scanningUsers.add(user.id);

  try {
    const [ohlcvMap, allSignals] = await Promise.all([
      fetchOHLCVData(),
      fetchAllBottomSignals(0),
    ]);

    await prog.delete().catch(() => {});

    const symbolSignals = allSignals.filter(s => s.symbol === symbolCode)
      .sort((a, b) => new Date(b.date) - new Date(a.date));

    if (symbolSignals.length === 0) {
      const embed = new EmbedBuilder()
        .setTitle(`🔍 コード検索: ${symbolCode}`)
        .setDescription(`BOTTOMシグナルは検出されていません。`)
        .setColor(COLOR_WARN)
        .setFooter({ text: DISCLAIMER })
        .setTimestamp();
      await user.send({ embeds: [embed] });
      await interaction.editReply({ content: `✅ ${symbolCode} — シグナルなし。DMを確認してください。`, ephemeral: true });
      return;
    }

    const scored = [];
    for (const info of symbolSignals) {
      const data = ohlcvMap.get(symbolCode);
      if (!data) {
        scored.push({
          symbol: symbolCode,
          name: info.name ?? symbolCode,
          score: 0, maxScore: 6, filters: [], atrPct: null,
          signalDate: info.date, signalPrice: info.entry,
          futurePrice: (info.eval5bd !== null && !isNaN(info.eval5bd)) ? info.eval5bd : null,
          futureDiff: info.perf5bd !== null ? Number(info.perf5bd).toFixed(2) : null,
          latestClose: null, change: '0.00',
          alertId: info.alertId,
        });
      } else {
        const r = screenSymbol(symbolCode, data, info.date, info.entry, info.eval5bd, info.perf5bd);
        if (r) {
          r.name = info.name;
          // Sniperモード満点の場合はバッジを付与
          r.sniperTag = r.sniperEnabled && r.sniperScore === (sniperLogic.conditions.length || 6);
          r.alertId = info.alertId;
          scored.push(r);
        }
      }
    }

    if (scored.length === 0) {
      const embed = new EmbedBuilder()
        .setTitle(`🔍 コード検索: ${symbolCode}`)
        .setDescription(`シグナルはありましたが、スコア計算に失敗しました。`)
        .setColor(COLOR_WARN)
        .setFooter({ text: DISCLAIMER })
        .setTimestamp();
      await user.send({ embeds: [embed] });
      await interaction.editReply({ content: `✅ ${symbolCode} — DMを確認してください。`, ephemeral: true });
      return;
    }

    scored.sort((a, b) => {
      if (a.score !== b.score) return b.score - a.score;
      return new Date(b.signalDate) - new Date(a.signalDate);
    });

    // Premium理由を取得（失敗してもスキャン続行）
    let codeReasonMap = new Map();
    try {
      if (config.PREMIUM_SPREADSHEET_ID) {
        codeReasonMap = await fetchPremiumReasonsByAlertIds(symbolSignals);
      }
    } catch (err) {
      console.warn('[code-search] Premium理由取得エラー（スキップ）:', err.message);
    }
    for (const r of scored) {
      if (r.alertId && codeReasonMap.has(r.alertId)) {
        r.premiumReason = codeReasonMap.get(r.alertId);
      }
    }

    const headerEmbed = new EmbedBuilder()
      .setTitle(`🔍 コード検索: ${symbolCode}`)
      .setDescription(
        `直近のBOTTOMシグナル: **${scored.length}件**\n全スコアを表示します。`
      )
      .setColor(COLOR)
      .setTimestamp();

    await sendResultDMs(user, scored, headerEmbed);
    await interaction.editReply({ content: `✅ ${symbolCode} — DMを確認してください。`, ephemeral: true });

  } catch (err) {
    console.error('[code-search] エラー:', err);
    await interaction.editReply({ content: `❌ エラーが発生しました: ${err.message}`, ephemeral: true });
    await user.send(`❌ エラー: ${err.message}`).catch(() => {});
  } finally {
    scanningUsers.delete(user.id);
  }
}

// ============================================================
// ヘルプ（ライブ実績表示）
// ============================================================
async function runPremiumScanButton(interaction) {
  const customId = String(interaction.customId || '');
  const symbolCode = customId.slice(PREMIUM_SCAN_BUTTON_PREFIX.length).trim().toUpperCase();

  if (!/^\d{3,4}[A-Z]?$/.test(symbolCode)) {
    return interaction.reply({
      content: 'このスキャンボタンの証券コードを読み取れませんでした。',
      ephemeral: true,
    });
  }

  if (!(await checkRole(interaction))) {
    return interaction.reply({
      content: 'このボタンを使うには専用ロールが必要です。',
      ephemeral: true,
    });
  }

  if (scanningUsers.has(interaction.user.id)) {
    return interaction.reply({
      content: '現在スキャン実行中です。少し待ってからもう一度押してください。',
      ephemeral: true,
    });
  }

  return runCodeSearch(interaction, interaction.user, symbolCode);
}

function buildHelpEmbed() {
  const sniperBacktest = sniperLogic.backtest;
  const sniperLive = statsCache?.sniperLive ?? null;
  const sniperBacktestLabel = sniperBacktest?.source === 'all' ? '全件データ' : '過去データ';
  const sniperBacktestText = sniperBacktest
    ? `${sniperBacktestLabel}: ${sniperBacktest.n}件 / 勝率 ${sniperBacktest.wr.toFixed(1)}% / 平均 ${(sniperBacktest.avg >= 0 ? '+' : '') + sniperBacktest.avg.toFixed(1)}%`
    : '集計データなし';
  const sniperLiveText = sniperLive && sniperLive.n > 0
    ? `運用開始後: ${sniperLive.n}件 / 勝率 ${sniperLive.wr.toFixed(1)}% / 平均 ${(sniperLive.avg >= 0 ? '+' : '') + sniperLive.avg.toFixed(2)}%`
    : '運用開始後: 0件 / 集計中';
  const sniperConditions = sniperLogic.conditions.length > 0
    ? `${sniperLogic.conditions.slice(0, 3).join(' / ')}\n${sniperLogic.conditions.slice(3).join(' / ')}`
    : '未設定';

  const embed = new EmbedBuilder()
    .setTitle('📖 天底極致スクリーニングBot — 使い方')
    .setColor(COLOR)
    .setDescription(
      'TradingViewのBOTTOMシグナルが点灯した銘柄を、テクニカル指標で**品質スコアリング**して表示するBotです。'
    )
    .addFields(
      {
        name: '🔍 基本操作',
        value:
          '`/scan` と入力して、2つの選択肢を選んでください。\n\n' +
          '**mode（分析タイプ）** — 下記参照\n' +
          '**range（対象期間 or 証券コード）**\n' +
          '　・当日 / 前日 / 1週間 / 1ヶ月 / 全期間 / 日付指定\n' +
          '　・コード検索の場合は証券コードを入力（例: 7203, 428A）',
      },
      {
        name: '🎯 Stable（5点以上・厳選）',
        value: '高品質銘柄のみ表示。上昇トレンド × 出来高急増 × 反発を同時確認した厳選候補。',
      },
      {
        name: '⚡ Aggressive（4点以上・広め）',
        value: 'より多くの候補を表示。大化け候補も含む幅広いスキャン。',
      },
      {
        name: '🔫 Sniper（勝率重視）',
        value: '勝率重視の正式モード。より厳しい条件すべてを満たした少数精鋭の候補だけを表示します。',
      },
      {
        name: '🔎 コード検索',
        value:
          '特定の銘柄が直近にBOTTOMシグナルが点灯したかを確認できます。\n' +
          'スコア0点も含めて全結果を表示します。',
      },
      {
        name: '📊 スコアリング条件（max 6点）',
        value:
          'スコアは**品質/信頼度**の指標です。\n' +
          '「上昇トレンド中の銘柄が、出来高を伴って反発する瞬間」を6条件で採点します。\n' +
          '```\n' +
          '① close > EMA25（中期トレンド）    1点\n' +
          '② MACD hist > 0    1点\n' +
          '③ ストキャス≥75    1点\n' +
          '④ BB位置≥80%    1点\n' +
          '⑤ 直近3日連続下落後    1点\n' +
          '⑥ ギャップアップ（始値>前終値）    1点\n' +
          '```',
      },
    );

  // ── ライブ実績 or フォールバック ──
  if (statsCache) {
    const s = statsCache;
    const fmtPf = (pf) => pf >= 999 ? ' -  ' : pf.toFixed(2);

    embed.addFields({
      name: `📈 スコア別実績（${s.total}シグナル集計）`,
      value:
        '```\n' +
        `Stable ★6: ${String(s.star6.n).padStart(3)}件 勝率${String(s.star6.wr).padStart(5)}% PF${fmtPf(s.star6.pf).padStart(5)} 平均${(s.star6.avg >= 0 ? '+' : '') + s.star6.avg}%\n` +
        `Stable ★5: ${String(s.star5.n).padStart(3)}件 勝率${String(s.star5.wr).padStart(5)}% PF${fmtPf(s.star5.pf).padStart(5)} 平均${(s.star5.avg >= 0 ? '+' : '') + s.star5.avg}%\n` +
        `Aggr.  ★4: ${String(s.star4.n).padStart(3)}件 勝率${String(s.star4.wr).padStart(5)}% PF${fmtPf(s.star4.pf).padStart(5)} 平均${(s.star4.avg >= 0 ? '+' : '') + s.star4.avg}%\n` +
        `全シグナル: ${String(s.all.n).padStart(3)}件 勝率${String(s.all.wr).padStart(5)}%            平均${(s.all.avg >= 0 ? '+' : '') + s.all.avg}%\n` +
        '```\n' +
        `最終更新: ${s.updatedAt}`,
    });

    embed.addFields({
      name: '🔫 Sniper モード',
      value:
        '```\n' +
        `${sniperConditions}\n\n` +
        `過去実績\n${sniperBacktestText}\n\n` +
        `運用実績\n${sniperLiveText}\n` +
        '```',
    });

    embed.addFields({
      name: '🏷️ ボラティリティタグ',
      value:
        '各銘柄にATR%に基づくリスク特性タグを表示します。\n' +
        '```\n' +
        '🟢LOW （ATR<3%） 安定型 — 値動き穏やか\n' +
        '🟡MID （3-6%）  中間型\n' +
        '🔴HIGH（6%+）   変動型 — 大化けも暴落もありうる\n' +
        '```',
    });
  } else {
    embed.addFields({
      name: '📈 実績データ',
      value: '起動直後のため集計中です。しばらくしてから再度 `/help` をお試しください。',
    });

    embed.addFields({
      name: '🔫 Sniper モード',
      value:
        '```\n' +
        `${sniperConditions}\n\n` +
        `過去実績\n${sniperBacktestText}\n\n` +
        `運用実績\n${sniperLiveText}\n` +
        '```',
    });

    embed.addFields({
      name: '🏷️ ボラティリティタグ',
      value:
        '各銘柄にATR%に基づくリスク特性タグを表示します。\n' +
        '```\n' +
        '🟢LOW （ATR<3%） 安定型 — 値動き穏やか\n' +
        '🟡MID （3-6%）  中間型\n' +
        '🔴HIGH（6%+）   変動型 — 大化けも暴落もありうる\n' +
        '```',
    });
  }

  embed.addFields({
    name: '⚠️ 注意事項',
    value:
      'このBotはテクニカル指標を機械的に集計する**情報提供ツール**であり、投資助言ではありません。\n' +
      'スコアは品質/信頼度を示す数値であり、株価の動向を予測・保証するものではありません。\n' +
      '**売買の最終判断は必ずご自身の責任で**行ってください。',
  });

  embed.setFooter({ text: 'Ken5 Investment Lab — Precision Trading Tool' });
  embed.setTimestamp();
  return embed;
}

// ============================================================
// スコアリングロジック承認デプロイ（管理者専用）
// ============================================================
async function runApproveUpdate(interaction) {
  const adminUserId = process.env.ADMIN_USER_ID;
  // ADMIN_USER_ID 未設定の場合も含め、IDが一致しない全ユーザーをブロック
  if (!adminUserId || interaction.user.id !== adminUserId) {
    return interaction.reply({ content: '❌ このコマンドは管理者専用です。', ephemeral: true });
  }

  const githubToken = process.env.GITHUB_TOKEN;
  const githubRepo  = process.env.GITHUB_REPO || 'Ken5-jp/screening-bot';
  if (!githubToken) {
    return interaction.reply({ content: '❌ GITHUB_TOKEN が未設定です。', ephemeral: true });
  }

  const target = interaction.options.getString('target') || 'all';
  const targetLabel = LOGIC_UPDATE_TARGETS.find(item => item.value === target)?.name || target;

  await interaction.reply({ content: `⏳ ${targetLabel} の承認ワークフローを起動中...`, ephemeral: true });

  const body = JSON.stringify({ ref: 'main', inputs: { target } });
  const [owner, repo] = githubRepo.split('/');
  const options = {
    hostname: 'api.github.com',
    path: `/repos/${owner}/${repo}/actions/workflows/deploy.yml/dispatches`,
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${githubToken}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(body),
      'User-Agent': 'DiscordBot (screening-bot, 1.0)',
    },
  };

  await new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      if (res.statusCode === 204) {
        resolve();
      } else {
        let data = '';
        res.on('data', chunk => { data += chunk; });
        res.on('end', () => reject(new Error(`GitHub API ${res.statusCode}: ${data}`)));
      }
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  }).then(async () => {
    await interaction.editReply({
      content: `✅ ${targetLabel} の承認ワークフローを起動しました。GitHub Actions で進捗を確認してください。`,
      ephemeral: true,
    });
  }).catch(async (err) => {
    console.error('[approve-update] GitHub API エラー:', err.message);
    await interaction.editReply({
      content: `❌ GitHub Actions の起動に失敗しました: ${err.message}`,
      ephemeral: true,
    });
  });
}

// ============================================================
// スコアリングロジック却下（管理者専用）
// ============================================================
async function runRejectUpdate(interaction) {
  const adminUserId = process.env.ADMIN_USER_ID;
  if (!adminUserId || interaction.user.id !== adminUserId) {
    return interaction.reply({ content: '❌ このコマンドは管理者専用です。', ephemeral: true });
  }

  const githubToken = process.env.GITHUB_TOKEN;
  const githubRepo  = process.env.GITHUB_REPO || 'Ken5-jp/screening-bot';
  if (!githubToken) {
    return interaction.reply({ content: '❌ GITHUB_TOKEN が未設定です。', ephemeral: true });
  }

  const target = interaction.options.getString('target') || 'all';
  const targetLabel = LOGIC_UPDATE_TARGETS.find(item => item.value === target)?.name || target;

  await interaction.reply({ content: `⏳ ${targetLabel} の却下ワークフローを起動中...`, ephemeral: true });

  const body = JSON.stringify({ ref: 'main', inputs: { target } });
  const [owner, repo] = githubRepo.split('/');
  const options = {
    hostname: 'api.github.com',
    path: `/repos/${owner}/${repo}/actions/workflows/reject.yml/dispatches`,
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${githubToken}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(body),
      'User-Agent': 'DiscordBot (screening-bot, 1.0)',
    },
  };

  await new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      if (res.statusCode === 204) {
        resolve();
      } else {
        let data = '';
        res.on('data', chunk => { data += chunk; });
        res.on('end', () => reject(new Error(`GitHub API ${res.statusCode}: ${data}`)));
      }
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  }).then(async () => {
    await interaction.editReply({
      content: `🗑️ ${targetLabel} の更新候補を却下するワークフローを起動しました。`,
      ephemeral: true,
    });
  }).catch(async (err) => {
    console.error('[reject-update] GitHub API エラー:', err.message);
    await interaction.editReply({
      content: `❌ GitHub Actions の起動に失敗しました: ${err.message}`,
      ephemeral: true,
    });
  });
}

// ============================================================
// Bot起動・コマンド登録
// ============================================================
client.once('ready', async () => {
  console.log(`✅ ${client.user.tag} 起動完了`);

  // ギルドコマンドが残っていれば削除（グローバルコマンドとの重複を防ぐ）
  if (config.GUILD_ID) {
    const guild = await client.guilds.fetch(config.GUILD_ID).catch(() => null);
    if (guild) await guild.commands.set([]);
  }

  // グローバル登録（サーバー内・BotDM両方で使えるようにする）
  await client.application.commands.set([
    {
      name: 'scan',
      description: 'BOTTOMシグナルのスクリーニングを実行',
      options: [
        {
          name: 'mode', type: 3, description: '分析タイプを選択', required: true,
          choices: [
            { name: '🎯 Stable（5点以上・厳選）',       value: 'stable' },
            { name: '⚡ Aggressive（4点以上・広め）',   value: 'aggressive' },
            { name: '🔫 Sniper（勝率重視）',             value: 'sniper' },
            { name: '🔎 コード検索（個別銘柄確認）',    value: 'code' },
          ],
        },
        {
          name: 'range', type: 3, required: true, autocomplete: true,
          description: '期間を選ぶか日付をYYYY-MM-DD形式で入力（コード検索は証券コード）',
        },
      ],
    },
    { name: 'help', description: 'Botの使い方とスコアの説明を表示' },
    {
      name: 'approve-update',
      description: '【管理者専用】保留中のスコアリングロジック更新を承認してデプロイ',
      options: [
        {
          name: 'target',
          type: 3,
          description: '承認するロジックを選択',
          required: true,
          autocomplete: true,
        },
      ],
    },
    {
      name: 'reject-update',
      description: '【管理者専用】保留中のスコアリングロジック更新を却下して削除',
      options: [
        {
          name: 'target',
          type: 3,
          description: '却下するロジックを選択',
          required: true,
          autocomplete: true,
        },
      ],
    },
  ]);
  console.log('スラッシュコマンド登録完了');

  // ★ 起動時に実績データを集計
  refreshStats();

  // ★ 24時間ごとに自動更新
  setInterval(refreshStats, 24 * 60 * 60 * 1000);
});

// ============================================================
// インタラクションハンドラ
// ============================================================
client.on('interactionCreate', async (interaction) => {

  if (interaction.isAutocomplete()) {
    const focused = interaction.options.getFocused();
    if (interaction.commandName === 'approve-update' || interaction.commandName === 'reject-update') {
      await interaction.respond(logicUpdateTargetChoices(focused));
      return;
    }
    const modeKey = interaction.options.getString('mode');

    if (modeKey === 'code') {
      if (/^\d/.test(focused)) {
        await interaction.respond([
          { name: `🔎 ${focused}（4桁の証券コードを入力）`, value: focused },
        ]);
      } else {
        await interaction.respond([
          { name: '4桁の証券コードを入力してください（例: 7203, 285A）', value: '0000' },
        ]);
      }
      return;
    }

    if (/^\d/.test(focused)) {
      const candidates = [];
      const today = new Date();
      for (let i = 0; i < 14; i++) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        const ds = d.toISOString().slice(0, 10);
        if (ds.startsWith(focused)) {
          candidates.push({
            name: i === 0 ? `📅 ${ds}（今日）` : i === 1 ? `📅 ${ds}（昨日）` : `📅 ${ds}`,
            value: ds,
          });
        }
      }
      await interaction.respond(candidates.slice(0, 25));
    } else {
      const fixed = [
        { name: '当日（今日出たシグナル）', value: '1' },
        { name: '前日（昨日出たシグナル）', value: 'yesterday' },
        { name: '1週間（最近7日間）',      value: '7' },
        { name: '1ヶ月（最近30日間）',    value: '30' },
        { name: '全期間（すべて）',        value: '0' },
      ];
      await interaction.respond(fixed.filter(c => c.name.includes(focused) || focused === ''));
    }
    return;
  }

  if (interaction.isButton()) {
    if (String(interaction.customId || '').startsWith(PREMIUM_SCAN_BUTTON_PREFIX)) {
      await runPremiumScanButton(interaction);
    }
    return;
  }

  if (!interaction.isChatInputCommand()) return;

  if (interaction.commandName === 'help') {
    return interaction.reply({ embeds: [buildHelpEmbed()], ephemeral: true });
  }
  if (interaction.commandName === 'scan') {
    await runScan(interaction);
  }
  if (interaction.commandName === 'approve-update') {
    await runApproveUpdate(interaction);
  }
  if (interaction.commandName === 'reject-update') {
    await runRejectUpdate(interaction);
  }
});

client.on('error', err => console.error('[discord] エラー:', err));

if (!config.DISCORD_TOKEN)   { console.error('❌ DISCORD_TOKEN 未設定'); process.exit(1); }
if (!config.SPREADSHEET_ID) { console.error('❌ SPREADSHEET_ID 未設定'); process.exit(1); }

client.login(config.DISCORD_TOKEN).catch(err => {
  console.error('❌ ログイン失敗:', err.message);
  process.exit(1);
});

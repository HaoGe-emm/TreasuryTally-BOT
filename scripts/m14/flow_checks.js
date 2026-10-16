  // Included inside the driver function; all actions use the actual page.
  await check("UR-02", async () => {
    if (!await page.getByRole("textbox", { name: "工作区 ID", exact: true }).isVisible()) {
      await page.getByText("运行配置", { exact: true }).click();
    }
    await page.getByRole("textbox", { name: "工作区 ID", exact: true }).fill(config.workspace);
    await page.getByRole("textbox", { name: "工作区 ID", exact: true }).press("Enter");
    await page.getByRole("button", { name: "生成可核对的任务候选", exact: true }).waitFor();
    const uploader = page.locator('input[type="file"]').first();
    await uploader.setInputFiles(config.report);
    await page.getByText(/已读取/).waitFor();
    await page.getByRole("textbox", { name: "核验范围说明", exact: true }).fill(config.scope);
    const draftButton = page.getByRole("button", { name: "生成可核对的任务候选", exact: true });
    await draftButton.focus();
    await draftButton.press("Enter");
    await page.getByRole("button", { name: "确认并冻结 TaskSpec", exact: true }).waitFor({ timeout: 90000 });
    await page.getByRole("spinbutton", { name: "Chain ID", exact: true }).fill(String(config.task.chain_id));
    await page.getByRole("textbox", { name: "代币地址", exact: true }).fill(config.task.token_address);
    await page.getByRole("spinbutton", { name: "起始区块（含）", exact: true }).fill(String(config.task.start_block));
    await page.getByRole("spinbutton", { name: "结束区块（含）", exact: true }).fill(String(config.task.end_block));
    await page.getByRole("textbox", { name: "资金账户（每行一个，最多两个）", exact: true }).fill(config.task.treasury_addresses.join("\n"));
    await page.getByRole("textbox", { name: "资助对象（每行一个）", exact: true }).fill(config.task.recipient_addresses.join("\n"));
    const exclusion = page.getByRole("checkbox", { name: "排除资金账户之间的内部互转", exact: true });
    if (await exclusion.isChecked() !== (config.task.exclusion_rules.length > 0)) {
      await exclusion.focus();
      await exclusion.press("Space");
    }
    await page.getByRole("button", { name: "确认并冻结 TaskSpec", exact: true }).click();
    await page.getByText("任务未确认：请先勾选任务边界确认框。", { exact: true }).waitFor();
    ensure(!await page.getByRole("button", { name: /开始验收/ }).count(), "unconfirmed task executed");
    const prior = results.find(item => item.id === "UR-06");
    prior.evidence.uncheckedConfirmationRejected = true;
    const confirmation = page.getByRole("checkbox", { name: "我已核对链、资产、账户与区块边界，并确认冻结此任务", exact: true });
    await confirmation.focus();
    await confirmation.press("Space");
    ensure(await confirmation.isChecked(), "keyboard confirmation failed");
    const freezeButton = page.getByRole("button", { name: "确认并冻结 TaskSpec", exact: true });
    await freezeButton.focus();
    await freezeButton.press("Enter");
    await page.getByRole("button", { name: "开始验收 · Attempt 1", exact: true }).waitFor();
    const runButton = page.getByRole("button", { name: "开始验收 · Attempt 1", exact: true });
    await runButton.focus();
    await runButton.press("Enter");
    await page.getByText(/验收通过/).first().waitFor({ timeout: 180000 });
    ensure((await page.locator("body").innerText()).includes(config.expectedTotal), "independent expected amount absent");
    const sourceDisclosure = page.locator("summary").filter({ hasText: "证据来源与采样诊断" }).first();
    await sourceDisclosure.focus();
    await sourceDisclosure.press("Enter");
    ensure((await page.locator("body").innerText()).includes("COMPLETE"), "real RPC completeness absent");
    await page.getByText("查看不可变任务指纹与完整边界", { exact: true }).click();
    const hash = await page.locator('code').filter({ hasText: /^0x[a-f0-9]{64}$/ }).first().innerText();
    return { workspace: config.workspace, expectedTotal: config.expectedTotal, taskHash: hash, realRpcComplete: true, keyboardActions: ["draft", "exclusion", "confirm", "freeze", "run", "source disclosure"], screenshot: await screen("independent-pass") };
  });
  const independent = results.find(item => item.id === "UR-02");
  const cold = results.find(item => item.id === "UR-03");
  if (independent.status === "PASS" && cold.status === "PASS") cold.evidence.independentInputCompleted = true;
  else if (cold.status === "PASS") { cold.status = "BLOCKED"; cold.reason = "cold screen verified but independent path incomplete"; }
  if (independent.status === "PASS") {
    const keyboard = results.find(item => item.id === "UR-13");
    if (keyboard.status === "BLOCKED") {
      keyboard.status = "PASS";
      keyboard.reason = "";
      keyboard.evidence.coreActions = independent.evidence.keyboardActions;
      keyboard.evidence.resultEvidenceOpened = true;
    }
    record("UR-14", "PASS", { steps: ["own JSON upload", "edit candidate", "explicit confirm", "live verification", "source disclosure"], screenshot: independent.evidence.screenshot });
    const responsive = results.find(item => item.id === "UR-12");
    const resultViews = [];
    for (const [width, height] of [[1440,1000],[390,844],[759,900],[761,900]]) {
      await page.setViewportSize({ width, height });
      const dimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: innerWidth }));
      resultViews.push({ width, height, ...dimensions, screenshot: await screen(`result-${width}`) });
      if (dimensions.scroll > dimensions.inner) responsive.status = "FAIL";
    }
    responsive.evidence.resultViews = resultViews;
    responsive.reason = "actual 200% browser zoom requires separate completion";
    await page.setViewportSize({ width: 1440, height: 1000 });
    await check("UR-11", async () => {
      await page.getByText("公共回执与 ERC-8004", { exact: true }).first().click();
      const body = await page.locator("body").innerText();
      ensure(body.includes("NOT_SUBMITTED"), "publication state absent");
      const write = page.getByRole("button", { name: "发布公开 JSON 回执", exact: true });
      if (await write.count()) ensure(await write.isDisabled(), "unauthorized publish enabled");
      return { state: "NOT_SUBMITTED", clickedWrite: false, screenshot: await screen("write-isolation") };
    });
    await check("UR-04", async () => {
      await page.reload();
      await page.getByText("运行配置", { exact: true }).waitFor();
      await page.getByText("运行配置", { exact: true }).click();
      await page.getByRole("textbox", { name: "工作区 ID", exact: true }).fill(config.workspace);
      await page.getByRole("textbox", { name: "工作区 ID", exact: true }).press("Enter");
      await page.getByText(/验收通过/).first().waitFor({ timeout: 45000 });
      await page.getByText("查看不可变任务指纹与完整边界", { exact: true }).click();
      const restoredHash = await page.locator('code').filter({ hasText: /^0x[a-f0-9]{64}$/ }).first().innerText();
      ensure(restoredHash === independent.evidence.taskHash, "restored task fingerprint changed");
      return { restoredHash, screenshot: await screen("restored"), coverage: "page reload only; process/new-context restore pending" };
    });
    const restore = results.find(item => item.id === "UR-04");
    if (restore.status === "PASS") { restore.status = "BLOCKED"; restore.reason = "application process restart not executed"; }
  }

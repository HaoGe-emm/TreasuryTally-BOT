async (page) => {
  const config = __M14_CONFIG__;
  const id = config.fault === "conflict" ? "UR-08" : "UR-07";
  page.setDefaultTimeout(45000);
  try {
    await page.getByText("运行配置", { exact: true }).waitFor();
    await page.getByText("运行配置", { exact: true }).click();
    await page.getByRole("textbox", { name: "工作区 ID", exact: true }).fill(config.workspace);
    await page.getByRole("textbox", { name: "工作区 ID", exact: true }).press("Enter");
    await page.locator('input[type="file"]').first().setInputFiles(config.report);
    await page.getByText(/已读取/).waitFor();
    await page.getByRole("textbox", { name: "核验范围说明", exact: true }).fill(config.scope);
    await page.getByRole("button", { name: "生成可核对的任务候选", exact: true }).click();
    await page.getByRole("button", { name: "确认并冻结 TaskSpec", exact: true }).waitFor({ timeout: 90000 });
    await page.getByRole("spinbutton", { name: "Chain ID", exact: true }).fill(String(config.task.chain_id));
    await page.getByRole("textbox", { name: "代币地址", exact: true }).fill(config.task.token_address);
    await page.getByRole("spinbutton", { name: "起始区块（含）", exact: true }).fill(String(config.task.start_block));
    await page.getByRole("spinbutton", { name: "结束区块（含）", exact: true }).fill(String(config.task.end_block));
    await page.getByRole("textbox", { name: "资金账户（每行一个，最多两个）", exact: true }).fill(config.task.treasury_addresses.join("\n"));
    await page.getByRole("textbox", { name: "资助对象（每行一个）", exact: true }).fill(config.task.recipient_addresses.join("\n"));
    const exclusion = page.getByRole("checkbox", { name: "排除资金账户之间的内部互转", exact: true });
    if (await exclusion.isChecked()) await page.getByText("排除资金账户之间的内部互转", { exact: true }).click();
    await page.getByText("我已核对链、资产、账户与区块边界，并确认冻结此任务", { exact: true }).click();
    await page.getByRole("button", { name: "确认并冻结 TaskSpec", exact: true }).click();
    await page.getByRole("button", { name: "开始验收 · Attempt 1", exact: true }).click();
    await page.locator(".attempt-card.outcome-INCONCLUSIVE").waitFor({ timeout: 180000 });
    await page.getByText("证据来源与采样诊断", { exact: true }).first().click();
    const text = await page.locator("body").innerText();
    if (!text.includes("不能形成服务负面结论")) throw new Error("missing neutral evidence warning");
    if (config.fault === "conflict" && !text.includes("SIMULATED-TEST-CONFLICT")) throw new Error("injected conflict not labelled");
    if (config.fault === "unavailable" && !text.includes("INCOMPLETE")) throw new Error("incomplete RPC not displayed");
    const screenshot = `${config.output}/fault-${config.fault}.png`;
    await page.screenshot({ path: screenshot, fullPage: true });
    return [{ id, status: "PASS", evidence: { fault: config.fault, browserOutcome: "INCONCLUSIVE", simulatedFault: true, screenshot }, reason: "" }];
  } catch (error) {
    return [{ id, status: "FAIL", evidence: { message: error.message }, reason: "fault browser assertion failed" }];
  }
}

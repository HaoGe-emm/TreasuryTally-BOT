async (page) => {
  const config = __M14_CONFIG__;
  page.setDefaultTimeout(45000);
  try {
    await page.getByText("运行配置", { exact: true }).waitFor();
    await page.getByText("运行配置", { exact: true }).click();
    await page.getByRole("textbox", { name: "工作区 ID", exact: true }).fill(config.workspace);
    await page.getByRole("textbox", { name: "工作区 ID", exact: true }).press("Enter");
    await page.locator(".attempt-card.outcome-PASS").first().waitFor();
    await page.getByText("查看不可变任务指纹与完整边界", { exact: true }).click();
    const hash = await page.locator("code").filter({ hasText: /^0x[a-f0-9]{64}$/ }).first().innerText();
    if (hash !== config.restoreTaskHash) throw new Error("task hash changed on process/fresh-context restore");
    if (!(await page.locator("body").innerText()).includes(config.expectedTotal)) throw new Error("restored amount changed");
    const screenshot = `${config.output}/process-restored.png`;
    await page.screenshot({ path: screenshot, fullPage: true });
    return [{ id: "UR-04", status: "PASS", evidence: {
      workspace: config.workspace, taskHash: hash, expectedTotal: config.expectedTotal,
      freshBrowserContext: true, screenshot,
      limitation: "Process restart must be corroborated by launcher command evidence; this run verifies persisted PASS task.",
    }, reason: "" }];
  } catch (error) {
    return [{ id: "UR-04", status: "FAIL", evidence: { message: error.message }, reason: "restoration failed" }];
  }
}

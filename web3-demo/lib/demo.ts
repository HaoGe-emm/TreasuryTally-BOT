import type { TaskSpec } from "./task";

// Public, user-confirmed demo binding. It is an application check; the original
// CommitmentAnchor contract does not enforce this identity relationship.
export const confirmedDemo = {
  taskId: "bot677-demo-usdt-26879920-two-accounts",
  specHash: "0x9e0073e83868993f4da3bc013fe8aca7e90af7a99fb80bcda8d593963528d093",
  typedDataDigest: "0x193954b4c310b54ac5b93bf9cb546d31f831f40b76378a100c53010d93fb7f2a",
  requester: "0x89F415bb42e356E8b892C10B05522e0a8Ef151F3",
  serviceId: "treasurytally-bot-internal-demo-20261016",
  serviceSigner: "0xb6bF6a936F529650992B71e2DeB79E80Fd3da71B"
} as const;

export function requireConfirmedDemoBinding(
  task: TaskSpec, requester: string, serviceId: string, serviceSigner: string
): void {
  if (task.spec_hash.toLowerCase() !== confirmedDemo.specHash ||
      task.task_id !== confirmedDemo.taskId || task.chain_id !== 677 ||
      requester.toLowerCase() !== confirmedDemo.requester.toLowerCase() ||
      serviceId.trim() !== confirmedDemo.serviceId ||
      serviceSigner.toLowerCase() !== confirmedDemo.serviceSigner.toLowerCase())
    throw new Error("BOT Demo 的请求者、服务 ID 或服务签名者与用户确认范围不符");
}

export function matchesConfirmedDemoBinding(
  task: TaskSpec, requester: string, serviceId: string, serviceSigner: string
): boolean {
  try {
    requireConfirmedDemoBinding(task, requester, serviceId, serviceSigner);
    return true;
  } catch {
    return false;
  }
}

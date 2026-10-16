import { createPublicClient, http, parseAbi, type Address, type Hex } from "viem";
import { botChain } from "./chain";

export const anchorAbi = parseAbi([
  "function tasks(address requester, bytes32 taskDigest) view returns (address requesterStored, address serviceSigner)",
  "function delivered(address requester, bytes32 taskDigest, uint8 attempt) view returns (bool)",
  "function anchorTask(bytes32 taskDigest, bytes32 specHash, bytes32 serviceIdHash, address serviceSigner)",
  "function anchorDelivery(address requester, bytes32 taskDigest, uint8 attempt, bytes32 submissionIdHash, bytes32 reportHash, bytes32 deliveryDigest)",
  "event TaskAnchored(bytes32 indexed taskDigest, address indexed requester, address indexed serviceSigner, bytes32 specHash, bytes32 serviceIdHash)",
  "event DeliveryAnchored(bytes32 indexed taskDigest, address indexed serviceSigner, uint8 indexed attempt, address requester, bytes32 submissionIdHash, bytes32 reportHash, bytes32 deliveryDigest)"
]);

export const publicClient = createPublicClient({
  chain: botChain, transport: http(undefined, { timeout: 8_000, retryCount: 0 })
});

const configuredAddress = process.env.NEXT_PUBLIC_ANCHOR_ADDRESS || "";
const configuredHash = process.env.NEXT_PUBLIC_ANCHOR_RUNTIME_SHA256 || "";
export const anchorAddress = /^0x[\da-fA-F]{40}$/.test(configuredAddress)
  ? configuredAddress as Address : null;
export const anchorRuntimeHash = /^0x[\da-fA-F]{64}$/.test(configuredHash)
  ? configuredHash.toLowerCase() as Hex : null;

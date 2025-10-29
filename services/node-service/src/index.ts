import amqp from "amqplib";
import axios from "axios";
import fs from "fs";
import path from "path";
import { mintNFT } from "./nftManager";


// solana endpoints
//"https://api.mainnet-beta.solana.com";
//"https://rpc.ankr.com/solana_devnet"; 
//"https://api.devnet.solana.com";
//"https://solana-rpc.publicnode.com";

// irys endpoints
// mainnet address: "https://node1.irys.xyz"
// devnet address: "https://devnet.irys.xyz"

const SOLANA_NETWORK = "devnet"; // "mainnet" | "devnet"
const KEYPAIR = "keypair_0.json";

interface Dictionary<T> {
    [key: string]: T;
}

const solanaEndpoints: Dictionary<string> = {
    "mainnet": "https://api.mainnet-beta.solana.com",
    "devnet": "https://api.devnet.solana.com",
}

const irysEndpoints: Dictionary<string> = {
    "mainnet": "https://node1.irys.xyz",
    "devnet": "https://devnet.irys.xyz",
}

declare const process: any;
declare const Buffer: any;

const walletFilePath = path.join(process.cwd(), 'src', KEYPAIR);
let walletFile: Buffer;
try {
  walletFile = fs.readFileSync(walletFilePath); //, "utf-8");
} catch (e) {
  console.error(`Failed to read keypair at ${walletFilePath}:`, e);
  // attempt to read relative path as fallback
  walletFile = fs.readFileSync(path.join(process.cwd(), KEYPAIR)); //, "utf-8");
}

interface TaskMessage {
  id: string;
  url: string;
  status: string;
}

async function start() {
  const conn = await amqp.connect("amqp://rabbitmq");
  const channel = await conn.createChannel();
  // ensure queue durability matches producer (durable: false)
  await channel.assertQueue("tasks", { durable: false });

  channel.on('error', (err: any) => {
    console.error('Channel error:', err);
  });
  conn.on('error', (err: any) => {
    console.error('Connection error:', err);
  });

  console.log(" [*] Waiting for messages...");

  channel.consume("tasks", async (msg: amqp.ConsumeMessage | null) => {
    if (!msg) return;

    try {
      const data: TaskMessage = JSON.parse(msg.content.toString());
      console.log(" [x] Received:", data);

      // Загружаем изображение из MinIO
      const response = await axios.get(data.url, { responseType: "arraybuffer" });

      const outDir = '/app/output';
      if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
      const filePath = `${outDir}/${data.id}.gif`;
      fs.writeFileSync(filePath, response.data);
      console.log(` [✔] Image saved as ${filePath}`);

      // Minting NFT (logs from the minting flow are printed by nftManager)
      const solanaEndpoint = solanaEndpoints[SOLANA_NETWORK];
      const irysEndpoint = irysEndpoints[SOLANA_NETWORK];
      await mintNFT(walletFile, solanaEndpoint, irysEndpoint, filePath, {
        name: `Neuro #${data.id}`,
        symbol: "NEUROTEST",
        description: "A unique Neuro NFT",
        attributes: [
          { trait_type: "game", value: "Neuro" },
          { trait_type: "version", value: "1.0" }
        ]
      }, { genome_version: "1.0" }, SOLANA_NETWORK);

      console.log(` [✔] NFT minted for NeuroKitty #${data.id}`);

      channel.ack(msg);
    } catch (err) {
      console.error(" [!] Error processing message:", err);
      channel.nack(msg, false, false); // не повторяем
    }
  });
}

start().catch(console.error);

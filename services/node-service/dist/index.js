"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const amqplib_1 = __importDefault(require("amqplib"));
const axios_1 = __importDefault(require("axios"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const nftManager_1 = require("./nftManager");
// solana endpoints
//"https://api.mainnet-beta.solana.com";
//"https://rpc.ankr.com/solana_devnet"; 
//"https://api.devnet.solana.com";
//"https://solana-rpc.publicnode.com";
// irys endpoints
// mainnet address: "https://node1.irys.xyz"
// devnet address: "https://devnet.irys.xyz"
const walletFilePath = path_1.default.join(process.cwd(), 'src', 'keypair_0.json');
let walletFile;
try {
    walletFile = fs_1.default.readFileSync(walletFilePath); //, "utf-8");
}
catch (e) {
    console.error(`Failed to read keypair at ${walletFilePath}:`, e);
    // attempt to read relative path as fallback
    walletFile = fs_1.default.readFileSync(path_1.default.join(process.cwd(), 'keypair_0.json')); //, "utf-8");
}
const solanaEndpoints = {
    "mainnet": "https://api.mainnet-beta.solana.com",
    "devnet": "https://api.devnet.solana.com",
};
const irysEndpoints = {
    "mainnet": "https://node1.irys.xyz",
    "devnet": "https://devnet.irys.xyz",
};
async function start() {
    const conn = await amqplib_1.default.connect("amqp://rabbitmq");
    const channel = await conn.createChannel();
    // ensure queue durability matches producer (durable: false)
    await channel.assertQueue("tasks", { durable: false });
    channel.on('error', (err) => {
        console.error('Channel error:', err);
    });
    conn.on('error', (err) => {
        console.error('Connection error:', err);
    });
    console.log(" [*] Waiting for messages...");
    channel.consume("tasks", async (msg) => {
        if (!msg)
            return;
        try {
            const data = JSON.parse(msg.content.toString());
            console.log(" [x] Received:", data);
            // Загружаем изображение из MinIO
            const response = await axios_1.default.get(data.url, { responseType: "arraybuffer" });
            const outDir = '/app/output';
            if (!fs_1.default.existsSync(outDir))
                fs_1.default.mkdirSync(outDir, { recursive: true });
            const filePath = `${outDir}/${data.id}.gif`;
            fs_1.default.writeFileSync(filePath, response.data);
            console.log(` [✔] Image saved as ${filePath}`);
            // Minting NFT (logs from the minting flow are printed by nftManager)
            const solanaEndpoint = solanaEndpoints["devnet"];
            const irysEndpoint = irysEndpoints["devnet"];
            await (0, nftManager_1.mintNFT)(walletFile, solanaEndpoint, irysEndpoint, filePath, {
                name: `NeuroKitty #${data.id}`,
                symbol: "NEUROKITTY",
                description: "A unique NeuroKitty NFT",
                attributes: [
                    { trait_type: "game", value: "NeuroKitties" },
                    { trait_type: "version", value: "1.0" }
                ]
            }, { genome_version: "1.0" });
            console.log(` [✔] NFT minted for NeuroKitty #${data.id}`);
            channel.ack(msg);
        }
        catch (err) {
            console.error(" [!] Error processing message:", err);
            channel.nack(msg, false, false); // не повторяем
        }
    });
}
start().catch(console.error);

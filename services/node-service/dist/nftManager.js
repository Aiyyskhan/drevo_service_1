"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.mintNFT = mintNFT;
exports.createNFT = createNFT;
const mpl_token_metadata_1 = require("@metaplex-foundation/mpl-token-metadata");
const umi_bundle_defaults_1 = require("@metaplex-foundation/umi-bundle-defaults");
const umi_1 = require("@metaplex-foundation/umi");
const serializers_1 = require("@metaplex-foundation/umi/serializers");
const umi_uploader_irys_1 = require("@metaplex-foundation/umi-uploader-irys");
const fs_1 = __importDefault(require("fs"));
function initUmi(walletFile, solanaEndpoint, irysEndpoint) {
    // Инициализация Umi
    const umi = (0, umi_bundle_defaults_1.createUmi)(solanaEndpoint);
    // Normalize walletFile into a Uint8Array (secret key bytes)
    let secretKeyUint8;
    try {
        if (Array.isArray(walletFile)) {
            secretKeyUint8 = Uint8Array.from(walletFile);
        }
        else if (walletFile instanceof Uint8Array) {
            secretKeyUint8 = walletFile;
        }
        else if (typeof walletFile === 'object' && walletFile !== null && typeof walletFile.toString === 'function') {
            const text = walletFile.toString();
            console.log('[initUmi] walletFile appears to be text; snippet:', text && text.slice ? text.slice(0, 200) : String(text));
            try {
                const parsed = JSON.parse(text);
                if (Array.isArray(parsed)) {
                    console.log('[initUmi] Parsed JSON array with length', parsed.length);
                    secretKeyUint8 = Uint8Array.from(parsed);
                }
                else if (parsed && typeof parsed === 'object') {
                    if (Array.isArray(parsed.secretKey)) {
                        console.log('[initUmi] Parsed object contains secretKey array, length', parsed.secretKey.length);
                        secretKeyUint8 = Uint8Array.from(parsed.secretKey);
                    }
                    else if (parsed._keypair && Array.isArray(parsed._keypair.secretKey)) {
                        console.log('[initUmi] Parsed object contains _keypair.secretKey array, length', parsed._keypair.secretKey.length);
                        secretKeyUint8 = Uint8Array.from(parsed._keypair.secretKey);
                    }
                    else {
                        const possible = parsed.secretKey || parsed.privateKey || parsed.key || undefined;
                        if (typeof possible === 'string') {
                            const b = Buffer.from(possible, 'base64');
                            if (b.length === 32 || b.length === 64)
                                secretKeyUint8 = new Uint8Array(b);
                            else
                                throw new Error('decoded base64 length is not 32 or 64');
                        }
                        else {
                            throw new Error('Unsupported JSON wallet shape');
                        }
                    }
                }
                else {
                    const b = Buffer.from(text, 'base64');
                    if (b.length === 32 || b.length === 64)
                        secretKeyUint8 = new Uint8Array(b);
                    else
                        throw new Error('decoded base64 length is not 32 or 64');
                }
            }
            catch (e) {
                console.log('[initUmi] walletFile text is not JSON, trying base64 decode');
                const b = Buffer.from(text, 'base64');
                if (b.length === 32 || b.length === 64)
                    secretKeyUint8 = new Uint8Array(b);
                else
                    throw new Error('Unsupported walletFile format: not JSON array/object or base64');
            }
        }
        else {
            throw new Error('Unsupported walletFile type');
        }
    }
    catch (err) {
        throw new Error(`Failed to parse walletFile into secret key bytes: ${err instanceof Error ? err.message : String(err)}`);
    }
    if (!secretKeyUint8)
        throw new Error('Failed to extract secret key bytes from walletFile');
    // Validate length: web3 Keypair expects a 64-byte secret key (or a 32-byte seed depending on API).
    if (!(secretKeyUint8.length === 64 || secretKeyUint8.length === 32)) {
        throw new Error(`bad secret key size: expected 32 or 64 bytes, got ${secretKeyUint8.length}`);
    }
    const keypair = umi.eddsa.createKeypairFromSecretKey(secretKeyUint8);
    const signer = (0, umi_1.createSignerFromKeypair)(umi, keypair);
    umi.use((0, umi_1.signerIdentity)(signer))
        .use((0, mpl_token_metadata_1.mplTokenMetadata)())
        .use((0, umi_uploader_irys_1.irysUploader)({ address: irysEndpoint }));
    return umi;
}
// Wrapper function expected by index.ts
async function mintNFT(walletFile, solanaEndpoint, irysEndpoint, filePath, partMetadata, genome_data) {
    // Read file and convert to base64 data URI
    const data = fs_1.default.readFileSync(filePath);
    const base64 = data.toString('base64');
    const dataUri = `data:image/gif;base64,${base64}`;
    // Initialize umi and perform upload + mint flow using existing helpers
    const umi = initUmi(walletFile, solanaEndpoint, irysEndpoint);
    console.log('[mintNFT] Uploading image...');
    const imageUri = await uploadImage(umi, dataUri, partMetadata.name);
    console.log('[mintNFT] Uploading metadata...');
    const metadata = { ...partMetadata, image: imageUri, properties: genome_data };
    const metadataUri = await uploadMetadata(umi, metadata);
    console.log('[mintNFT] Minting NFT on Solana...');
    await mint(umi, metadataUri, metadata.name, metadata.symbol);
    console.log('[mintNFT] Mint process finished.');
}
async function createNFT(wallet, solanaEndpoint, irysEndpoint, base64Image, partMetadata, genome_data) {
    const umi = initUmi(wallet, solanaEndpoint, irysEndpoint);
    const imageUri = await uploadImage(umi, base64Image, partMetadata.name);
    const metadata = { ...partMetadata, image: imageUri, properties: genome_data };
    const metadataUri = await uploadMetadata(umi, metadata);
    await mint(umi, metadataUri, metadata.name, metadata.symbol);
}
async function uploadImage(umi, base64Image, kitty_name) {
    try {
        // Support environments with and without Node Buffer (browser)
        const base64Data = base64Image.includes(',') ? base64Image.split(',')[1] : base64Image;
        let imageBytes;
        const globalBuffer = globalThis.Buffer;
        if (globalBuffer && typeof globalBuffer.from === 'function') {
            imageBytes = globalBuffer.from(base64Data, 'base64');
        }
        else {
            // Fallback for browsers: use atob -> Uint8Array
            const binary = atob(base64Data);
            const len = binary.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++)
                bytes[i] = binary.charCodeAt(i);
            imageBytes = bytes;
        }
        const umiImageFile = (0, umi_1.createGenericFile)(imageBytes, `${kitty_name}.gif`, {
            displayName: kitty_name,
            uniqueName: kitty_name,
            contentType: 'image/gif',
        });
        const imageUri = await umi.uploader.upload([umiImageFile]);
        console.log(`Image uploaded, URI: ${imageUri[0]}`);
        return imageUri[0];
    }
    catch (err) {
        if (err instanceof Error)
            throw err;
        throw new Error(String(err));
    }
}
async function uploadMetadata(umi, metadata) {
    try {
        console.log('Uploading metadata...');
        const metadataUri = await umi.uploader.uploadJson(metadata);
        console.log('Metadata uploaded, URI:', metadataUri);
        return metadataUri;
    }
    catch (err) {
        if (err instanceof Error)
            throw err;
        throw new Error(String(err));
    }
}
async function mint(umi, metadataUri, kitty_name, kitty_symbol) {
    try {
        const nftSigner = (0, umi_1.generateSigner)(umi);
        const tx = await (0, mpl_token_metadata_1.createNft)(umi, {
            mint: nftSigner,
            name: kitty_name,
            symbol: kitty_symbol,
            uri: metadataUri,
            sellerFeeBasisPoints: (0, umi_1.percentAmount)(5.5),
        }).sendAndConfirm(umi);
        const signature = serializers_1.base58.deserialize(tx.signature)[0];
        console.log("\nNFT Created");
        try {
            const endpoint = umi.rpc && typeof umi.rpc.getEndpoint === 'function' ? umi.rpc.getEndpoint() : 'unknown-endpoint';
            console.log("View Transaction (endpoint):", `${endpoint}/tx/${signature}`);
            console.log("View NFT (mint address):", String(nftSigner.publicKey));
        }
        catch (e) {
            console.log("Mint completed. Signature:", signature);
        }
    }
    catch (err) {
        if (err instanceof Error)
            throw err;
        throw new Error(String(err));
    }
}
// (remaining commented helpers omitted)
// async function umiTest(umi: Umi) {
//     const endpoint = umi.rpc.getEndpoint();
//     const cluster = umi.rpc.getCluster();
//     console.log("Endpoint: " + endpoint);
//     console.log("Cluster: " + cluster);
//     console.log("umi pubkey: " + umi.identity.publicKey);
//     const balance = await umi.rpc.getBalance(umi.identity.publicKey);
//     console.log(`Balance: ${JSON.stringify(balance, (_, value) => typeof value === "bigint" ? Number(value) : value)}`);
// }
// async function airdrop(umi: Umi) {
//     // This will airdrop SOL on devnet only for testing.
//     await umi.rpc.airdrop(umi.identity.publicKey, sol(1.5));
// }
// export async function getNFTs(wallet: Wallet, solanaEndpoint: string): Promise<FullMetadata[] | null | undefined> {
//     const umi = initUmi(wallet, solanaEndpoint);
//     try {    
//         console.log("Получение списка NFT...");
//         const assets = await fetchAllDigitalAssetWithTokenByOwner(umi, umi.identity.publicKey);
//         const neuroKittyNFTs = await Promise.all(
//             assets.map(async (nft) => {
//                 try {
//                     const resp = await fetch(nft.metadata.uri);
//                     if (!resp.ok) {
//                         // throw new Error(`Ошибка HTTP при запросе metadata: ${resp.status}`);
//                         console.error(`Ошибка HTTP при запросе metadata: ${resp.status}`);                        
//                         return null;
//                     }
//                     const metadata: FullMetadata = await resp.json();
//                     if (
//                             metadata.name.startsWith("NeuroKitty") &&
//                             metadata.attributes.some(attr => attr.trait_type === "game" && attr.value === "NeuroKitties") &&
//                             metadata.attributes.some(attr => attr.trait_type === "version" && attr.value === config.GAME_VERSION)
//                     ) {
//                         return {
//                             name: metadata.name,
//                             symbol: metadata.symbol || "",
//                             description: metadata.description || "No description available",
//                             attributes: metadata.attributes || [],
//                             properties: {},
//                             image: metadata.image,
//                         };
//                     }
//                 } catch (err) {
//                     console.error("Failed to fetch metadata for:", nft.metadata.uri, err);
//                     return null;
//                 }
//             })
//         );
//         return neuroKittyNFTs.filter(Boolean) as FullMetadata[];
//     } catch (error) {
//         console.error("Ошибка:", error);
//     }
// }
// export async function sendDonation(wallet: Wallet, solanaEndpoint: string, recipientAddr: string, amount: number) {
//     const umi = initUmi(wallet, solanaEndpoint);
//     const donationAddress = publicKey(recipientAddr);
//     const donationAmount = sol(amount); // Convert to lamports (1 SOL = 1,000,000,000 lamports)
//     try {
//         const tx = await transferSol(umi, {
//             source: umi.identity,
//             destination: donationAddress,
//             amount: donationAmount,
//         }).sendAndConfirm(umi);
//         const signature = base58.deserialize(tx.signature)[0];
//         console.log("Donation sent successfully!");
//         console.log("View Transaction on Solana Explorer");
//         console.log(`${config.SOLANA.EXPLORER}/tx/${signature}?cluster=${config.SOLANA.NET}`);
//     } catch (error) {
//         console.error("Error sending donation:", error);
//     }
// }

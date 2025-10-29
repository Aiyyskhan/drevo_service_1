import { Keypair } from "@solana/web3.js";
import { createNft, fetchAllDigitalAssetWithTokenByOwner, mplTokenMetadata } from "@metaplex-foundation/mpl-token-metadata";
import { createUmi } from '@metaplex-foundation/umi-bundle-defaults'
import { createSignerFromKeypair, signerIdentity, createGenericFile, generateSigner, percentAmount, Umi, sol, publicKey } from "@metaplex-foundation/umi";
import { base58 } from "@metaplex-foundation/umi/serializers";
import { irysUploader } from "@metaplex-foundation/umi-uploader-irys";
import { fromWeb3JsKeypair } from '@metaplex-foundation/umi-web3js-adapters';
import fs from 'fs';

// Minimal local type aliases to avoid missing type errors in this repo
export type GenomeType = Record<string, unknown>;
export type UmiPlugin = any;

export type MetadataAttributesType = {
    trait_type: string,
    value: string,
}

export interface PartialMetadata {
    name: string;
    symbol: string;
    description: string;
    attributes: MetadataAttributesType[];
}

export interface FullMetadata extends PartialMetadata {
    image: string;
    // Store genome or arbitrary properties from metadata
    properties: GenomeType | Record<string, unknown>;
}

function initUmi(walletFile: any, solanaEndpoint: string, irysEndpoint: string): Umi {
    // Инициализация Umi
    const umi = createUmi(solanaEndpoint);

    const secret = JSON.parse(fs.readFileSync("src/keypair_0.json", "utf-8"));
    const web3jsKeypair = Keypair.fromSecretKey(Uint8Array.from(secret));

    // const keypair = umi.eddsa.createKeypairFromSecretKey(secretKeyUint8);
    const umiKeypair = fromWeb3JsKeypair(web3jsKeypair);

    const signer = createSignerFromKeypair(umi, umiKeypair);

    umi.use(signerIdentity(signer))
        .use(mplTokenMetadata())
        .use(irysUploader({ address: irysEndpoint }));

    return umi;
}

// Wrapper function expected by index.ts
export async function mintNFT(walletFile: any, solanaEndpoint: string, irysEndpoint: string, filePath: string, partMetadata: PartialMetadata, genome_data: GenomeType | Record<string, unknown>, network: string = "devnet") {
    // Read file and convert to base64 data URI
    const data = fs.readFileSync(filePath);
    const base64 = data.toString('base64');
    const dataUri = `data:image/gif;base64,${base64}`;

    // Initialize umi and perform upload + mint flow using existing helpers
    const umi = initUmi(walletFile, solanaEndpoint, irysEndpoint);

    console.log('[mintNFT] Uploading image...');
    const imageUri = await uploadImage(umi, dataUri, partMetadata.name);

    console.log('[mintNFT] Uploading metadata...');
    const metadata: FullMetadata = { ...partMetadata, image: imageUri, properties: genome_data };
    const metadataUri = await uploadMetadata(umi, metadata);

    console.log('[mintNFT] Minting NFT on Solana...');
    await mint(umi, metadataUri, metadata.name, metadata.symbol, network);
    console.log('[mintNFT] Mint process finished.');
}

async function uploadImage(umi: Umi, base64Image: string, kitty_name: string): Promise<string> {
    try {
        // Support environments with and without Node Buffer (browser)
        const base64Data = base64Image.includes(',') ? base64Image.split(',')[1] : base64Image;
        let imageBytes: Uint8Array;

        const globalBuffer = (globalThis as unknown as { Buffer?: { from?: (s: string, enc?: string) => Uint8Array } }).Buffer;
        if (globalBuffer && typeof globalBuffer.from === 'function') {
            imageBytes = globalBuffer.from(base64Data, 'base64');
        } else {
            // Fallback for browsers: use atob -> Uint8Array
            const binary = atob(base64Data);
            const len = binary.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
            imageBytes = bytes;
        }

        const umiImageFile = createGenericFile(
            imageBytes,
            `${kitty_name}.gif`,
            {
                displayName: kitty_name,
                uniqueName: kitty_name,
                contentType: 'image/gif',
            }
        );

        const imageUri = await umi.uploader.upload([umiImageFile]);

        console.log(`Image uploaded, URI: ${imageUri[0]}`);
        return imageUri[0];
    } catch (err) {
        if (err instanceof Error) throw err;
        throw new Error(String(err));
    }
}

async function uploadMetadata(umi: Umi, metadata: FullMetadata): Promise<string> {
    try {
        console.log('Uploading metadata...');

        const metadataUri = await umi.uploader.uploadJson(metadata);

        console.log('Metadata uploaded, URI:', metadataUri);
        return metadataUri;     
    } catch (err) {
        if (err instanceof Error) throw err;
        throw new Error(String(err));
    }
}

async function mint(umi: Umi, metadataUri: string, kitty_name: string, kitty_symbol: string, network: string) {
    try {
        const nftSigner = generateSigner(umi);

        const tx = await createNft(umi, {
            mint: nftSigner,
            name: kitty_name,
            symbol: kitty_symbol,
            uri: metadataUri,
            sellerFeeBasisPoints: percentAmount(5.5),
        }).sendAndConfirm(umi)

        const signature = base58.deserialize(tx.signature)[0];

        console.log("\nNFT Created");
        try {
            const endpoint = umi.rpc && typeof umi.rpc.getEndpoint === 'function' ? umi.rpc.getEndpoint() : 'unknown-endpoint';
            console.log("View Transaction:", `https://explorer.solana.com/tx/${signature}?cluster=${network}`);
            console.log("View NFT:", `https://explorer.solana.com/address/${nftSigner.publicKey}?cluster=${network}`);
        } catch (e) {
            console.log("Mint completed. Signature:", signature);
        }
    } catch (err) {
        if (err instanceof Error) throw err;
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
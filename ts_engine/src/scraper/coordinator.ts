import { z } from 'zod';
import { type VideoResult, VideoResultSchema } from '../queue/celery';

/**
 * Scraper Interface
 */
export interface Scraper {
  discover(query: string): Promise<VideoResult[]>;
  readonly platformName: string;
}

/**
 * Mock Generic Scraper
 */
export class GenericScraper implements Scraper {
  constructor(public readonly platformName: string) {}

  async discover(query: string): Promise<VideoResult[]> {
    // Simulasi delay jaringan
    await new Promise((resolve) => setTimeout(resolve, 1000));
    
    // Mock result generator
    const rawResult = {
      Platform: this.platformName,
      VideoURL: `https://mock.url/${this.platformName.toLowerCase()}/${Date.now()}`,
      Title: `[Trending] ${query} on ${this.platformName}`,
      Views: Math.floor(Math.random() * 1000000),
      Published: new Date().toISOString(),
    };

    // Validasi Zod secara run-time
    const parsed = VideoResultSchema.parse(rawResult);
    return [parsed];
  }
}

/**
 * Discovery Coordinator
 */
export class DiscoveryCoordinator {
  private scrapers: Scraper[];

  constructor(scrapers: Scraper[]) {
    this.scrapers = scrapers;
  }

  async runAll(query: string): Promise<VideoResult[]> {
    console.log(`🔥 Mencari konten viral untuk: '${query}'...`);
    
    const promises = this.scrapers.map(async (scraper) => {
      try {
        return await scraper.discover(query);
      } catch (error) {
        console.error(`⚠️ Scraper Error pada platform ${scraper.platformName}:`, error);
        return [];
      }
    });

    const resultsArray = await Promise.all(promises);
    const finalResults = resultsArray.flat();
    
    console.log(`📊 Ditemukan ${finalResults.length} total video dari berbagai platform.`);
    return finalResults;
  }
}

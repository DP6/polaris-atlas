import { httpClient } from '@/lib/http-client'
import type {
  BucketObjectsResponse,
  BucketsListResponse,
  MinDaysUnused,
  WasteCandidatesResponse,
} from '@/types/storage'

export const storageApi = {
  getBuckets: (projectId: string) =>
    httpClient.get<BucketsListResponse>(`/api/v1/storage/${projectId}/buckets`),

  getWasteCandidates: (projectId: string, minDaysUnused: MinDaysUnused = 60) =>
    httpClient.get<WasteCandidatesResponse>(
      `/api/v1/storage/${projectId}/waste-candidates?min_days_unused=${minDaysUnused}`,
    ),

  browseBucket: (
    projectId: string,
    bucketName: string,
    options?: { prefix?: string; pageToken?: string },
  ) => {
    const params = new URLSearchParams()
    if (options?.prefix) params.set('prefix', options.prefix)
    if (options?.pageToken) params.set('page_token', options.pageToken)
    const query = params.toString()
    return httpClient.get<BucketObjectsResponse>(
      `/api/v1/storage/${projectId}/${encodeURIComponent(bucketName)}/objects${query ? `?${query}` : ''}`,
    )
  },
}

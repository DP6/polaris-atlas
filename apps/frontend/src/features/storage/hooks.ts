import { useQuery } from '@tanstack/react-query'
import { storageApi } from '@/lib/api/storage'

export function useBuckets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['storage', 'buckets', projectId],
    queryFn: () => storageApi.getBuckets(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useBucketObjects(
  projectId: string | undefined,
  bucketName: string | undefined,
  prefix: string | undefined,
  pageToken: string | undefined,
) {
  return useQuery({
    queryKey: ['storage', 'bucket-objects', projectId, bucketName, prefix, pageToken],
    queryFn: () =>
      storageApi.browseBucket(projectId as string, bucketName as string, { prefix, pageToken }),
    enabled: Boolean(projectId) && Boolean(bucketName),
  })
}

export function useWasteCandidates(
  projectId: string | undefined,
  minDaysUnused = 60,
  enabled = true,
) {
  return useQuery({
    queryKey: ['storage', 'waste-candidates', projectId, minDaysUnused],
    queryFn: () => storageApi.getWasteCandidates(projectId as string, minDaysUnused),
    enabled: Boolean(projectId) && enabled,
  })
}

import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/app/layout'
import { AdminPage } from '@/features/admin/AdminPage'
import { RequireAdmin } from '@/features/admin/RequireAdmin'
import { AuthCallbackPage } from '@/features/auth/AuthCallbackPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CatalogDatasetPage } from '@/features/catalog/CatalogDatasetPage'
import { CatalogOverviewPage } from '@/features/catalog/CatalogOverviewPage'
import { SearchPage } from '@/features/catalog/SearchPage'
import { FavoritesPage } from '@/features/favorites/FavoritesPage'
import { RecentsPage } from '@/features/favorites/RecentsPage'
import { BudgetPage } from '@/features/finops/BudgetPage'
import { ColumnTypesPage } from '@/features/finops/ColumnTypesPage'
import { FinOpsOverviewPage } from '@/features/finops/FinOpsOverviewPage'
import { PartitionCandidatesPage } from '@/features/finops/PartitionCandidatesPage'
import { ScannerOverviewPage } from '@/features/finops/ScannerOverviewPage'
import { DatasetFreshnessPage } from '@/features/freshness/DatasetFreshnessPage'
import { FreshnessPage } from '@/features/freshness/FreshnessPage'
import { GovernanceOverviewPage } from '@/features/governance/GovernanceOverviewPage'
import { LineagePage } from '@/features/lineage/LineagePage'
import { OrphansPage } from '@/features/lineage/OrphansPage'
import { MetadataAnalysisPage } from '@/features/metadata/MetadataAnalysisPage'
import { MetadataOverviewPage } from '@/features/metadata/MetadataOverviewPage'
import { NotFoundPage } from '@/features/misc/NotFoundPage'
import { AccessAnalysisPage } from '@/features/quality/AccessAnalysisPage'
import { AnalysisChooserPage } from '@/features/quality/AnalysisChooserPage'
import { AnalysisLayout } from '@/features/quality/AnalysisLayout'
import { ColumnTypesAnalysisPage } from '@/features/quality/ColumnTypesAnalysisPage'
import { HistoryAnalysisPage } from '@/features/quality/HistoryAnalysisPage'
import { PiiAnalysisPage } from '@/features/quality/PiiAnalysisPage'
import { QualityAnalysisPage } from '@/features/quality/QualityAnalysisPage'
import { QualityFolderComparisonPage } from '@/features/quality/QualityFolderComparisonPage'
import { QualityFoldersPage } from '@/features/quality/QualityFoldersPage'
import { QualityTablesPage } from '@/features/quality/QualityTablesPage'
import { SchemaAnalysisPage } from '@/features/quality/SchemaAnalysisPage'
import { BucketBrowserPage } from '@/features/storage/BucketBrowserPage'
import { BucketsPage } from '@/features/storage/BucketsPage'
import { StorageOverviewPage } from '@/features/storage/StorageOverviewPage'
import { WastePage } from '@/features/storage/WastePage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<CatalogOverviewPage />} />
          <Route path="datasets/:datasetId" element={<CatalogDatasetPage />} />
          <Route path="favoritos" element={<FavoritesPage />} />
          <Route path="recentes" element={<RecentsPage />} />
          <Route path="governanca" element={<GovernanceOverviewPage />} />
          <Route path="freshness" element={<FreshnessPage />} />
          <Route path="freshness/:datasetId" element={<DatasetFreshnessPage />} />
          <Route path="orphans" element={<OrphansPage />} />
          <Route path="metadados" element={<MetadataOverviewPage />} />
          <Route path="lineage/:datasetId/:tableId" element={<LineagePage />} />
          {/* "Análises de qualidade" na sidebar mostra só o caminho das
              análises salvas (pastas) — rodada 3. */}
          <Route path="quality" element={<Navigate to="/quality/folders" replace />} />
          <Route path="quality/tables" element={<QualityTablesPage />} />
          <Route path="quality/folders" element={<QualityFoldersPage />} />
          <Route path="quality/folders/:folderId" element={<QualityFolderComparisonPage />} />
          <Route path="analyze/:datasetId/:tableId" element={<AnalysisLayout />}>
            <Route index element={<AnalysisChooserPage />} />
            <Route path="schema" element={<SchemaAnalysisPage />} />
            <Route path="quality" element={<QualityAnalysisPage />} />
            <Route path="pii" element={<PiiAnalysisPage />} />
            <Route path="column-types" element={<ColumnTypesAnalysisPage />} />
            <Route path="history" element={<HistoryAnalysisPage />} />
            <Route path="access" element={<AccessAnalysisPage />} />
            <Route path="metadata" element={<MetadataAnalysisPage />} />
          </Route>
          <Route path="finops" element={<FinOpsOverviewPage />} />
          <Route path="finops/scanner" element={<ScannerOverviewPage />} />
          <Route path="finops/scanner/particionamento" element={<PartitionCandidatesPage />} />
          <Route path="finops/scanner/tipos-coluna" element={<ColumnTypesPage />} />
          <Route path="finops/budget" element={<BudgetPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="storage" element={<StorageOverviewPage />} />
          <Route path="storage/buckets" element={<BucketsPage />} />
          <Route path="storage/waste" element={<WastePage />} />
          <Route path="storage/:bucketName" element={<BucketBrowserPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="admin" element={<AdminPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

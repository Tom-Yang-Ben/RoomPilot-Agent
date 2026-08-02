# RoomPilot AWS RDS PostgreSQL 雲端部署、驗收與交接手冊

更新日期：2026-08-02（Asia/Taipei）

## 1. 文件目的

本文件是 RoomPilot 家具 catalog 與家具向量上 AWS RDS for PostgreSQL 的正式 Runbook，包含：

- AWS IAM、RDS、VPC、Security Group 與 Secrets Manager 的責任分界。
- 家具及向量匯入順序。
- 正式筆數、pgvector 與 SSL 驗收方式。
- Snapshot、唯讀 API 帳號與團隊交接規則。
- 後端上雲後將 RDS 改為 Private 的安全切換程序。
- PostgreSQL Engine 與 extension 升級後的檢查方式。

本文件不得包含真實密碼、AWS Access Key、Root 憑證、完整 RDS endpoint 或個人公開 IP。

## 2. 最重要的憑證分界

| 憑證 | 用途 | 可以交給誰 |
| --- | --- | --- |
| AWS Root | 帳號救援、付款、少數 Root-only 操作 | 不交付；只由帳號擁有者保管並啟用 MFA |
| roompilot-cloud-admin IAM／SSO | 建立及管理 RDS、Security Group、Snapshot、Secrets Manager | 不共用；每位 AWS 操作者使用自己的 IAM／SSO 身分 |
| AWS Access Key | AWS CLI／SDK 呼叫 AWS API | 不放 Git、README、.env 或聊天；不交給一般組員 |
| PostgreSQL roompilot_master | Schema、migration、正式匯入、管理 DB role | 只供受控管理流程使用；密碼留在 AWS Secrets Manager |
| PostgreSQL roompilot_api | 後端唯讀家具 catalog／向量 | 由 Secrets Manager 或 CI/CD 注入後端；不得授予寫入或管理權限 |

AWS Access Key 管理 AWS 資源；PostgreSQL 帳密連線資料庫。兩者完全不同。

## 3. 目前已驗證的正式狀態

| 項目 | 狀態 |
| --- | --- |
| Region | ap-east-2 |
| RDS identifier | roompilot-postgres-prod |
| Engine | PostgreSQL 17.10 |
| Database | roompilot_db |
| RDS status | available |
| Encryption | 已啟用 |
| Deletion protection | 已啟用 |
| Auto minor version upgrade | 已啟用 |
| SSL | verify-full，連線驗證通過 |
| pg_trgm | 1.6 |
| pgvector | 0.8.2 |
| Master secret | AWS Secrets Manager 管理 |
| API role | roompilot_api，唯讀 |
| Manual snapshot | roompilot-initial-import-20260802-2232，available、encrypted、20 GiB |
| Public access | 目前仍為 True；必須等後端 SG 就緒後才可關閉 |
| RDS inbound | 目前只允許管理者 IP/32；不得改為 0.0.0.0/0 |

注意：初始 Snapshot 建立於 roompilot_api 角色之前。若由該 Snapshot 還原，須重新建立 roompilot_api，或在權限設定完成後另建一份最終 Snapshot。

## 4. 正式資料契約

| 物件 | 正式筆數 |
| --- | ---: |
| furniture_items | 8,675 |
| active_furniture | 8,076 |
| inactive_furniture | 599 |
| furniture_assets | 34,700 |
| furniture_catalog_api_current | 8,076 |
| furniture_embedding_source_current | 8,076 |
| furniture_embeddings | 8,076 |
| furniture_categories | 56 |
| styles | 6 |
| rooms | 9 |
| furniture_vlm_annotations | 8,675 |

向量契約：

- Model：BAAI/bge-m3
- Dimension：1024
- Distance：cosine
- L2 normalized：true
- pgvector：0.8.2
- HNSW index：目前為 0，這是現行 schema 刻意要求的狀態
- Contract probe rows：0，代表測試模型未誤命中正式資料

## 5. 最終執行順序與目前狀態

狀態說明：

- 已驗證：已由 CLI、PostgreSQL 或匯入器確認。
- 使用者回報完成：屬於 Root／MFA／本機 dry-run 等無法由目前 DB 驗收反推的步驟。
- 待處理：尚未具備安全前置條件。

| # | 步驟 | 狀態 |
| ---: | --- | --- |
| 1 | Root 開啟 MFA | 使用者／AWS Console 確認 |
| 2 | Root 建立 roompilot-cloud-admins Group | 使用者／AWS Console 確認 |
| 3 | Attach AmazonRDSFullAccess | 使用者／IAM 確認 |
| 4 | Attach RoomPilotRDSNetworkAdmin | 使用者／IAM 確認 |
| 5 | Attach SecretsManagerReadWrite | 使用者／IAM 確認 |
| 6 | 建立 roompilot-cloud-admin | 已驗證 caller identity |
| 7 | roompilot-cloud-admin 開啟 MFA | 使用者／AWS Console 確認 |
| 8 | 設定 AWS CLI SSO 或 Access Key | 已可使用 roompilot-cloud-admin profile |
| 9 | aws sts get-caller-identity | 已驗證 |
| 10 | 確認 ap-east-2 支援 PostgreSQL 17.10 | 已驗證 |
| 11 | 建立 RDS Security Group | 已驗證 |
| 12 | 只開管理者 IP/32 | 已驗證；非 0.0.0.0/0 |
| 13 | 建立 DB Subnet Group | 已驗證 |
| 14 | 建立 RDS PostgreSQL 17.10 | 已驗證 |
| 15 | 取得 Endpoint 與 Secrets Manager 密碼 | 已驗證；未落地 Master 密碼 |
| 16 | 下載 RDS CA Bundle | 已驗證 |
| 17 | 測試 SSL 連線 | 已驗證 |
| 18 | 家具 dry-run | 使用者回報完成 |
| 19 | 向量 dry-run | 使用者回報完成 |
| 20 | 正式匯入家具 | 已完成並 commit |
| 21 | 正式匯入向量 | 已完成並 commit |
| 22 | 驗證正式筆數與 extensions | 已驗證 |
| 23 | 建立 Snapshot | 已完成 |
| 24 | 建立 roompilot_api DB User | 已完成並驗證唯讀 |
| 25 | 組員只拿 API／有限 DB 權限 | .env.example 已記錄交接邊界 |
| 26 | 後端上雲後關閉 RDS Public Access | 待處理；尚無後端專用 SG |

## 6. AWS CLI 基本變數

以下只放非敏感變數：

~~~powershell
$PROFILE_NAME = "roompilot-cloud-admin"
$REGION_NAME = "ap-east-2"
$DB_INSTANCE_ID = "roompilot-postgres-prod"
$DB_NAME = "roompilot_db"
~~~

確認 AWS 身分：

~~~powershell
aws sts get-caller-identity --profile $PROFILE_NAME
~~~

確認 RDS 狀態：

~~~powershell
aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID --region $REGION_NAME --profile $PROFILE_NAME --query "DBInstances[0].{Status:DBInstanceStatus,Engine:Engine,EngineVersion:EngineVersion,PubliclyAccessible:PubliclyAccessible,AutoMinorVersionUpgrade:AutoMinorVersionUpgrade,DeletionProtection:DeletionProtection}" --output table
~~~

不得將 AWS Secret Access Key 寫入專案 .env。

## 7. 後端安全環境變數

可交付給後端的非敏感範本已放在 repository 根目錄 .env.example：

~~~dotenv
DB_HOST=roompilot-postgres-prod.REPLACE_ME.ap-east-2.rds.amazonaws.com
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=roompilot_api
DB_PASSWORD=
DB_SSLMODE=verify-full
PGSSLROOTCERT=/app/certs/global-bundle.pem
DB_CONNECT_TIMEOUT=15
DB_APPLICATION_NAME=roompilot_api
~~~

規則：

- DB_PASSWORD 必須由 AWS Secrets Manager、部署平台或 CI/CD 注入。
- 不得把真實 endpoint 或密碼 commit 到 Git。
- 前端不得直接連 PostgreSQL。
- 本機管理用 .env 已被 .gitignore 排除。
- Master 只用於受控 schema／migration／匯入，不作為後端 runtime 帳號。

## 8. SSL 連線驗證

本機管理者從 .env 載入設定後，以 psql 驗證：

~~~powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" "host=$env:DB_HOST port=$env:DB_PORT dbname=$env:DB_NAME user=$env:DB_USER sslmode=verify-full sslrootcert=$env:PGSSLROOTCERT" -c "SELECT current_database(), current_user, version();"
~~~

預期：

- Database：roompilot_db
- Runtime user：roompilot_api
- PostgreSQL：17.10
- SSL：verify-full

## 9. 本機 Dry Run

所有指令從 D:\RoomPilot-Agent 執行：

~~~powershell
Set-Location "D:\RoomPilot-Agent"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py --catalog JSON\furniture\furniture_official_catagory.json --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl --require-all --dry-run
~~~

Dry Run 不連線 PostgreSQL，也不寫入資料庫。

## 10. 正式匯入

正式匯入必須使用 roompilot_master，而不是目前唯讀的 roompilot_api。

Master 密碼應在單一管理 session 中從 AWS Secrets Manager 暫時載入，不得永久寫進 repository。

家具：

~~~powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py
~~~

向量：

~~~powershell
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py --catalog JSON\furniture\furniture_official_catagory.json --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl --require-all
~~~

兩個 importer 都會先驗證資料契約，成功後 commit，失敗則 rollback。

## 11. pgvector 與正式筆數驗收

Extension：

~~~sql
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('vector', 'pg_trgm')
ORDER BY extname;
~~~

正式筆數：

~~~sql
SELECT 'furniture_items' AS object_name, COUNT(*) FROM roompilot.furniture_items
UNION ALL
SELECT 'active_furniture', COUNT(*) FROM roompilot.furniture_items WHERE is_active
UNION ALL
SELECT 'inactive_furniture', COUNT(*) FROM roompilot.furniture_items WHERE NOT is_active
UNION ALL
SELECT 'furniture_assets', COUNT(*) FROM roompilot.furniture_assets
UNION ALL
SELECT 'catalog_api_current', COUNT(*) FROM roompilot.furniture_catalog_api_current
UNION ALL
SELECT 'embedding_source_current', COUNT(*) FROM roompilot.furniture_embedding_source_current
UNION ALL
SELECT 'furniture_embeddings', COUNT(*) FROM roompilot.furniture_embeddings;
~~~

驗收結果必須為：

~~~text
furniture_items          8675
active_furniture         8076
inactive_furniture        599
furniture_assets        34700
catalog_api_current      8076
embedding_source_current 8076
furniture_embeddings     8076
~~~

## 12. Snapshot

建立匯入後 Snapshot：

~~~powershell
$SNAPSHOT_ID = "roompilot-initial-import-$(Get-Date -Format yyyyMMdd-HHmm)"
aws rds create-db-snapshot --db-instance-identifier $DB_INSTANCE_ID --db-snapshot-identifier $SNAPSHOT_ID --region $REGION_NAME --profile $PROFILE_NAME
aws rds wait db-snapshot-available --db-snapshot-identifier $SNAPSHOT_ID --region $REGION_NAME --profile $PROFILE_NAME
~~~

目前已建立：

~~~text
roompilot-initial-import-20260802-2232
status=available
encrypted=true
engine=postgres 17.10
allocated_storage=20 GiB
~~~

## 13. roompilot_api 最小權限

建立角色時產生高強度密碼，且不要把密碼放進 SQL 檔：

~~~sql
CREATE ROLE roompilot_api
WITH LOGIN
PASSWORD '由安全流程注入'
NOSUPERUSER
NOCREATEDB
NOCREATEROLE
NOREPLICATION
NOBYPASSRLS;

GRANT CONNECT ON DATABASE roompilot_db TO roompilot_api;
GRANT USAGE ON SCHEMA roompilot TO roompilot_api;

GRANT SELECT ON roompilot.furniture_catalog_current TO roompilot_api;
GRANT SELECT ON roompilot.furniture_catalog_api_current TO roompilot_api;
GRANT SELECT ON roompilot.furniture_embedding_source_current TO roompilot_api;
GRANT SELECT ON roompilot.furniture_embeddings TO roompilot_api;
~~~

已驗證：

- 四個正式物件均可 SELECT。
- INSERT、UPDATE、DELETE 均為 false。
- 不使用 GRANT ALL。
- 若後端需要 project／workflow 寫入，必須由資料表 owner 逐表審核後另行授權。

## 14. 團隊交接

### 前端

前端只拿：

- 後端 API URL。
- API 文件。
- 家具欄位說明。
- CloudFront 圖片與 GLB URL 回傳格式。

前端不拿：

- PostgreSQL 帳密。
- AWS Access Key。
- Root 或 roompilot-cloud-admin。
- Security Group 管理權限。

### 後端

後端拿：

- 非敏感 DB host／port／database／user／SSL 設定。
- roompilot_api 密碼的 Secret reference 或部署注入。
- CA bundle 與容器掛載路徑。

後端必須交付 SQL/catalog owner：

- 部署平台與 VPC。
- 後端 Security Group ID。
- Secret 注入目的地。
- CA bundle 掛載路徑。
- 實際需要的資料表與讀寫權限範圍。

### RAG

RAG 組員交付：

- furniture_embeddings_bge_m3.jsonl。
- embedding model。
- dimension。
- normalized 狀態。
- text_hash。
- 產生時間。
- 驗證報告。

RAG 組員不需要 Master 帳密。

### AWS 操作者

每人使用獨立 IAM Identity Center／IAM 身分，並只提供：

- 個人身分名稱／email。
- 需要完成的工作。
- 最小權限範圍與期限。

不得共用 roompilot-cloud-admin 或 Access Key。

## 15. RDS Private 網路切換

### 目前狀態

- RDS PubliclyAccessible=True。
- RDS SG 只允許管理者 IP/32。
- 尚未找到後端專用 Security Group。
- roompilot-cloud-admin 目前無 ec2:DescribeInstances 與 ecs:ListClusters，無法完整盤點 EC2／ECS。
- 因此目前不得關閉 Public Access，也不得移除管理者 IP。

### 切換前必要條件

1. 後端已部署到同一 VPC。
2. 已取得後端服務的 Security Group ID。
3. 後端 SG 已允許必要 outbound。
4. RDS SG 已允許後端 SG 連入 TCP 5432。
5. 已從後端 runtime 使用 roompilot_api 與 SSL 成功連線。
6. 已確認 Snapshot 可用。
7. 才能關閉 Public Access。
8. 關閉後再次從後端驗證，再移除管理者 IP。

範本變數：

~~~powershell
$RDS_SG_ID = "sg-REPLACE_ME"
$BACKEND_SG_ID = "sg-REPLACE_ME"
$MY_IP = "REPLACE_ME/32"
~~~

先允許後端 SG：

~~~powershell
aws ec2 authorize-security-group-ingress --group-id $RDS_SG_ID --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$BACKEND_SG_ID,Description='RoomPilot backend to RDS'}]" --region $REGION_NAME --profile $PROFILE_NAME
~~~

從後端驗證連線後，將 RDS 改為 Private：

~~~powershell
aws rds modify-db-instance --db-instance-identifier $DB_INSTANCE_ID --no-publicly-accessible --apply-immediately --region $REGION_NAME --profile $PROFILE_NAME
aws rds wait db-instance-available --db-instance-identifier $DB_INSTANCE_ID --region $REGION_NAME --profile $PROFILE_NAME
~~~

再次從後端驗證後，才移除本機 IP：

~~~powershell
aws ec2 revoke-security-group-ingress --group-id $RDS_SG_ID --protocol tcp --port 5432 --cidr $MY_IP --region $REGION_NAME --profile $PROFILE_NAME
~~~

禁止：

- 在沒有後端 SG 的情況下關閉 Public Access。
- 先刪除管理者 IP，再測試後端。
- 將 5432 開放為 0.0.0.0/0。
- 讓前端直接連 PostgreSQL。

最終架構：

~~~text
Internet
   |
Backend API
   |
Backend Security Group
   |
Private RDS PostgreSQL
~~~

## 16. PostgreSQL 與 extension 升級

目前：

- PostgreSQL 17.10。
- AutoMinorVersionUpgrade=True。
- pgvector 0.8.2。

Engine 次版本升級後必須重新查詢：

~~~sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
~~~

只有在 RDS 已提供相容新版 extension、完成 Snapshot 並通過變更審核後，才以 Master 執行：

~~~sql
ALTER EXTENSION vector UPDATE;
~~~

注意：

- Engine 自動次版本升級不等於 extension 自動升級。
- roompilot_api 不得擁有 ALTER EXTENSION 權限。
- 升級後必須重跑 extension、正式筆數、向量 search function 與 API health 驗收。

## 17. 安全檢查清單

- [ ] Root 與管理身分均已啟用 MFA。
- [ ] 沒有 Root Access Key。
- [ ] 每位 AWS 操作者使用獨立 IAM／SSO 身分。
- [ ] Git 不包含 .env、DB 密碼或 AWS Access Key。
- [ ] Master 密碼只留在 AWS Secrets Manager。
- [ ] 後端只使用 roompilot_api 或經審核的應用角色。
- [ ] RDS SG 沒有 0.0.0.0/0 的 5432 規則。
- [ ] Snapshot 狀態為 available 且加密。
- [ ] 正式筆數符合本文件契約。
- [ ] pgvector 版本已驗證。
- [ ] 後端 SG 連線通過後才將 RDS 改為 Private。

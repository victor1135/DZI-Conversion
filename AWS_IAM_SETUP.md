# AWS IAM 权限配置指南

## 问题诊断

如果看到 `AccessDenied` 错误，说明：
- ✅ AWS 凭证已正确设置
- ❌ IAM 用户缺少 S3 写入权限

## 解决方案

### 方法 1：使用 AWS 管理控制台（推荐）

#### 步骤 1：创建 IAM 用户

1. 登录 [AWS 控制台](https://console.aws.amazon.com/)
2. 进入 **IAM** 服务
3. 点击左侧 **"Users"** → **"Create user"**
4. 输入用户名（例如：`dzi-converter-user`）
5. 选择 **"Provide user access to the AWS Management Console"**（可选）
6. 点击 **"Next"**

#### 步骤 2：附加权限策略

选择以下选项之一：

**选项 A：使用预定义策略（简单）**
- 选择 **"Attach policies directly"**
- 搜索并选择：**`AmazonS3FullAccess`**
- ⚠️ **注意**：这会授予所有 S3 bucket 的完全访问权限

**选项 B：自定义策略（推荐，更安全）**

1. 选择 **"Attach policies directly"**
2. 点击 **"Create policy"**
3. 切换到 **"JSON"** 标签
4. 粘贴以下策略：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::2026-demo",
                "arn:aws:s3:::2026-demo/*"
            ]
        }
    ]
}
```

**重要**：将 `2026-demo` 替换为您的实际 bucket 名称！

5. 点击 **"Next"** → 输入策略名称（例如：`DZIConverterS3Access`）
6. 点击 **"Create policy"**
7. 返回用户创建页面，刷新策略列表
8. 选择刚创建的策略

#### 步骤 3：创建访问密钥

1. 完成用户创建
2. 点击新创建的用户
3. 切换到 **"Security credentials"** 标签
4. 滚动到 **"Access keys"** 部分
5. 点击 **"Create access key"**
6. 选择 **"Application running outside AWS"**
7. 点击 **"Next"**
8. 可选：添加描述标签
9. 点击 **"Create access key"**
10. **重要**：立即复制并保存：
    - **Access key ID**
    - **Secret access key**（只显示一次！）

#### 步骤 4：在 Railway 中设置环境变量

将复制的凭证添加到 Railway 环境变量：

```
AWS_ACCESS_KEY_ID = <您的 Access Key ID>
AWS_SECRET_ACCESS_KEY = <您的 Secret Access Key>
AWS_BUCKET = 2026-demo
AWS_REGION = eu-west-2
S3_PUBLIC = true
```

---

### 方法 2：使用 AWS CLI

如果您已经安装了 AWS CLI：

```bash
# 1. 创建策略文件
cat > dzi-converter-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::2026-demo",
                "arn:aws:s3:::2026-demo/*"
            ]
        }
    ]
}
EOF

# 2. 创建策略
aws iam create-policy \
    --policy-name DZIConverterS3Access \
    --policy-document file://dzi-converter-policy.json

# 3. 创建用户
aws iam create-user --user-name dzi-converter-user

# 4. 附加策略到用户（替换 YOUR_ACCOUNT_ID 和 POLICY_ARN）
aws iam attach-user-policy \
    --user-name dzi-converter-user \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/DZIConverterS3Access

# 5. 创建访问密钥
aws iam create-access-key --user-name dzi-converter-user
```

---

## 权限说明

### 必需的 S3 操作

| 操作 | 说明 | 必需性 |
|------|------|--------|
| `s3:PutObject` | 上传文件到 S3 | ✅ 必需 |
| `s3:PutObjectAcl` | 设置文件 ACL（如果使用 public bucket） | ⚠️ 推荐 |
| `s3:GetObject` | 读取文件（用于验证） | ⚠️ 推荐 |
| `s3:ListBucket` | 列出 bucket 内容（用于调试） | ⚠️ 推荐 |
| `s3:DeleteObject` | 删除文件（如果需要清理） | ⚪ 可选 |

### 最小权限策略（仅上传）

如果您只需要上传功能，可以使用这个最小权限策略：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
        }
    ]
}
```

---

## 验证权限

### 使用 AWS CLI 测试

```bash
# 设置凭证
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-west-2"

# 测试上传
echo "test" > test.txt
aws s3 cp test.txt s3://2026-demo/test.txt

# 如果成功，应该看到：
# upload: ./test.txt to s3://2026-demo/test.txt

# 清理测试文件
aws s3 rm s3://2026-demo/test.txt
rm test.txt
```

### 使用 Python 测试

```python
import boto3

s3 = boto3.client(
    's3',
    aws_access_key_id='your-access-key',
    aws_secret_access_key='your-secret-key',
    region_name='eu-west-2'
)

# 测试上传
try:
    s3.put_object(
        Bucket='2026-demo',
        Key='test.txt',
        Body=b'test content'
    )
    print("✅ 上传成功！权限配置正确")
except Exception as e:
    print(f"❌ 上传失败: {e}")
```

---

## 常见问题

### Q: 为什么需要 `s3:PutObjectAcl`？

**A:** 如果您的 bucket 是 public 的，并且您希望上传的文件也是 public 可访问的，需要这个权限来设置 ACL。

### Q: 可以使用 `AmazonS3FullAccess` 吗？

**A:** 可以，但不推荐。这个策略会授予所有 S3 bucket 的完全访问权限，存在安全风险。建议使用自定义策略，只授予特定 bucket 的权限。

### Q: 如何限制只能访问特定路径？

**A:** 在策略的 `Resource` 中指定路径：

```json
{
    "Resource": [
        "arn:aws:s3:::2026-demo/dzi/*"  // 只能访问 dzi/ 路径下的文件
    ]
}
```

### Q: 凭证泄露了怎么办？

**A:** 立即：
1. 登录 AWS IAM 控制台
2. 找到对应的用户
3. 删除泄露的访问密钥
4. 创建新的访问密钥
5. 更新 Railway 环境变量

---

## 安全最佳实践

1. ✅ **最小权限原则**：只授予必要的权限
2. ✅ **定期轮换密钥**：每 90 天更换一次访问密钥
3. ✅ **使用 IAM 角色**：如果可能，使用 IAM 角色而不是用户
4. ✅ **启用 MFA**：为 IAM 用户启用多因素认证
5. ✅ **监控访问**：使用 CloudTrail 监控 S3 访问

---

## 下一步

配置完成后：

1. ✅ 在 Railway 中设置环境变量
2. ✅ 重新部署服务
3. ✅ 测试上传功能

如果仍然遇到 `AccessDenied` 错误，检查：
- Bucket 名称是否正确
- Region 是否正确
- IAM 策略是否正确附加到用户
- 访问密钥是否属于正确的用户

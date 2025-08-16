<!--篮子编辑器-->
<!--篮子编辑器-->
<script>
import { fetchBasketDetail, createBasket, updateBasket } from './api/basket.ts'
import StockSelector from '../../components/data/StockSelector'

export default {
  name: "BasketEditor",
  components: { StockSelector },
  data() {
    return {
      basket: {
        id: null,
        name: '',
        description: '',
        items: []
      },
      isEditMode: false,
      loading: false,
      rules: {
        name: [
          { required: true, message: '请输入篮子名称', trigger: 'blur' }
        ]
      }
    }
  },
  created() {
    const basketId = this.$route.params.id
    if (basketId) {
      this.isEditMode = true
      this.getBasketDetail(basketId)
    }
  },
  methods: {
    async getBasketDetail(basketId) {
      this.loading = true
      try {
        const response = await fetchBasketDetail(basketId)
        this.basket = response.data
      } catch (error) {
        console.error('获取篮子详情失败:', error)
        this.$message.error('获取数据失败')
      } finally {
        this.loading = false
      }
    },

    handleAddStock(selectedStock) {
      // 避免重复添加
      if (this.basket.items.some(item => item.ts_code === selectedStock.ts_code)) {
        this.$message.warning('该股票已在篮子中')
        return
      }

      this.basket.items.push({
        ts_code: selectedStock.ts_code,
        name: selectedStock.name,
        weight: 0
      })
    },

    handleRemoveStock(index) {
      this.basket.items.splice(index, 1)
    },

    async saveBasket() {
      // 权重总和校验
      const totalWeight = this.basket.items.reduce((sum, item) => sum + (item.weight || 0), 0)
      if (Math.abs(totalWeight - 1) > 0.01) {
        this.$message.error('成分股权重总和必须为100%')
        return
      }

      this.loading = true
      try {
        if (this.isEditMode) {
          await updateBasket(this.basket.id, this.basket)
          this.$message.success('篮子更新成功')
        } else {
          await createBasket(this.basket)
          this.$message.success('篮子创建成功')
        }
        this.$router.push({ name: 'BasketList' })
      } catch (error) {
        console.error('保存失败:', error)
        this.$message.error('保存失败')
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<template>
  <div class="basket-editor">
    <el-page-header
      @back="$router.go(-1)"
      :content="isEditMode ? '编辑篮子' : '新建篮子'" />

    <el-form
      v-loading="loading"
      :model="basket"
      :rules="rules"
      label-width="100px"
      label-position="top"
      class="basket-form">

      <el-form-item label="篮子名称" prop="name">
        <el-input
          v-model="basket.name"
          placeholder="请输入篮子名称"
          maxlength="50"
          show-word-limit />
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="basket.description"
          type="textarea"
          :rows="3"
          placeholder="请输入篮子描述"
          maxlength="200"
          show-word-limit />
      </el-form-item>

      <el-form-item label="添加成分股">
        <stock-selector @select="handleAddStock" />
      </el-form-item>

      <el-divider>成分股权重设置</el-divider>

      <div class="stocks-list">
        <div v-if="basket.items.length === 0" class="empty-tip">
          请添加成分股
        </div>

        <div v-for="(item, index) in basket.items" :key="index" class="stock-item">
          <div class="stock-info">
            <span class="code">{{ item.ts_code }}</span>
            <span class="name">{{ item.name }}</span>
          </div>

          <div class="weight-control">
            <el-input-number
              v-model="item.weight"
              :min="0"
              :max="1"
              :step="0.01"
              :precision="2"
              size="small"
              controls-position="right" />
            <span class="percent">%</span>
          </div>

          <el-button
            type="danger"
            icon="el-icon-delete"
            circle
            size="mini"
            @click="handleRemoveStock(index)" />
        </div>
      </div>

      <div class="form-actions">
        <el-button type="primary" @click="saveBasket">保存</el-button>
        <el-button @click="$router.go(-1)">取消</el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.basket-editor {
  padding: 20px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,.1);
}

.basket-form {
  margin-top: 20px;
  max-width: 800px;
}

.stocks-list {
  margin-top: 20px;
}

.stock-item {
  display: flex;
  align-items: center;
  padding: 12px 15px;
  margin-bottom: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background-color: #fafafa;
}

.stock-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.stock-info .code {
  font-weight: bold;
  margin-bottom: 4px;
}

.stock-info .name {
  font-size: 12px;
  color: #666;
}

.weight-control {
  display: flex;
  align-items: center;
  margin: 0 20px;
}

.weight-control .percent {
  margin-left: 8px;
  width: 30px;
}

.empty-tip {
  text-align: center;
  padding: 20px;
  color: #999;
  border: 1px dashed #ebeef5;
  border-radius: 4px;
  background-color: #fafafa;
}

.form-actions {
  margin-top: 30px;
  text-align: center;
}
</style>
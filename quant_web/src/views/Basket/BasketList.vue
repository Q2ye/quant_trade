<!--篮子列表-->
<!--篮子列表-->
<script>
import { fetchBasketList, deleteBasket } from '@/api/basket'

export default {
  name: "BasketList",
  data() {
    return {
      baskets: [],
      loading: false,
      pagination: {
        page: 1,
        pageSize: 10,
        total: 0
      }
    }
  },
  mounted() {
    this.getBasketList()
  },
  methods: {
    async getBasketList() {
      this.loading = true
      try {
        const params = {
          page: this.pagination.page,
          page_size: this.pagination.pageSize
        }
        const res = await fetchBasketList(params)
        this.baskets = res.data.items
        this.pagination.total = res.data.total
      } catch (error) {
        console.error('获取篮子列表失败:', error)
        this.$message.error('获取数据失败')
      } finally {
        this.loading = false
      }
    },

    handleCreate() {
      this.$router.push({ name: 'BasketEditor' })
    },

    handleEdit(id) {
      this.$router.push({ name: 'BasketEditor', params: { id } })
    },

    handleViewDetail(id) {
      this.$router.push({ name: 'BasketDetail', params: { id } })
    },

    async handleDelete(id) {
      this.$confirm('确定删除该篮子吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(async () => {
        try {
          await deleteBasket(id)
          this.$message.success('删除成功')
          this.getBasketList()
        } catch (error) {
          console.error('删除失败:', error)
          this.$message.error('删除失败')
        }
      })
    },

    handlePageChange(page) {
      this.pagination.page = page
      this.getBasketList()
    }
  }
}
</script>

<template>
  <div class="basket-list">
    <div class="header">
      <h2>股票篮子管理</h2>
      <el-button type="primary" icon="el-icon-plus" @click="handleCreate">
        新建篮子
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="baskets"
      stripe
      style="width: 100%">
      <el-table-column prop="name" label="篮子名称" min-width="150" />
      <el-table-column label="创建时间" min-width="150">
        <template slot-scope="scope">
          {{ scope.row.created_at | formatDate }}
        </template>
      </el-table-column>
      <el-table-column label="成分股数量" min-width="120">
        <template slot-scope="scope">
          {{ scope.row.items_count }} 只
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="200">
        <template slot-scope="scope">
          <el-button
            size="mini"
            type="primary"
            @click="handleViewDetail(scope.row.id)">
            详情
          </el-button>
          <el-button
            size="mini"
            @click="handleEdit(scope.row.id)">
            编辑
          </el-button>
          <el-button
            size="mini"
            type="danger"
            @click="handleDelete(scope.row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pagination"
      :current-page="pagination.page"
      :page-size="pagination.pageSize"
      :total="pagination.total"
      layout="total, sizes, prev, pager, next, jumper"
      @current-change="handlePageChange"
    />
  </div>
</template>

<style scoped>
.basket-list {
  padding: 20px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,.1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}
</style>
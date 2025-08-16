<template>
  <el-dialog
      :title="`交易确认 - ${currentSignal.symbol} ${currentSignal.name}`"
      :visible.sync="visible"
      width="500px"
      @close="resetForm"
  >
    <el-form :model="form" label-width="80px" :rules="rules" ref="tradeForm">
      <el-form-item label="交易方向">
        <el-radio-group v-model="form.direction">
          <el-radio-button label="BUY">买入</el-radio-button>
          <el-radio-button label="SELL">卖出</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="价格类型">
        <el-radio-group v-model="form.priceType">
          <el-radio-button label="LIMIT">限价</el-radio-button>
          <el-radio-button label="MARKET">市价</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="委托价格" prop="price" v-if="form.priceType === 'LIMIT'">
        <el-input-number
            v-model="form.price"
            :precision="2"
            :step="0.01"
            :min="0.01"
            controls-position="right"
        ></el-input-number>
        <span class="price-tips">
          最新价: {{ currentSignal.lastPrice }}
          <span :class="currentSignal.change >= 0 ? 'up' : 'down'">
            ({{ currentSignal.change >= 0 ? '+' : '' }}{{ currentSignal.change }}%)
          </span>
        </span>
      </el-form-item>

      <el-form-item label="委托数量" prop="quantity">
        <el-input-number
            v-model="form.quantity"
            :min="100"
            :step="100"
            controls-position="right"
        ></el-input-number>
        <span class="quantity-tips">
          可{{ form.direction === 'BUY' ? '买' : '卖' }}:
          {{ form.direction === 'BUY' ? availableCash : currentSignal.availableShares }}股
        </span>
      </el-form-item>

      <el-form-item label="总金额">
        <span class="total-amount">
          {{
            (form.price * form.quantity).toLocaleString('zh-CN', {
              style: 'currency',
              currency: 'CNY',
              minimumFractionDigits: 2
            })
          }}
        </span>
      </el-form-item>

      <el-form-item label="交易账户">
        <el-select v-model="form.account" placeholder="选择交易账户">
          <el-option
              v-for="acc in accounts"
              :key="acc.id"
              :label="`${acc.name} (${acc.broker})`"
              :value="acc.id"
          ></el-option>
        </el-select>
      </el-form-item>
    </el-form>

    <div slot="footer" class="dialog-footer">
      <el-button @click="visible = false">取 消</el-button>
      <el-button type="primary" @click="submitForm" :loading="submitting">确 定</el-button>
    </div>
  </el-dialog>
</template>

<script>
import {ref, reactive, watch} from 'vue';

export default {
  name: "TradeForm",
  props: {
    signal: {
      type: Object,
      default: () => ({
        symbol: '',
        name: '',
        lastPrice: 0,
        change: 0,
        availableShares: 0,
        recommendation: 'BUY' // 确保默认值包含recommendation
      })
    },
    accounts: {
      type: Array,
      default: () => []
    }
  },

  setup(props, {emit}) {
    const visible = ref(false);
    const tradeForm = ref(null);
    const submitting = ref(false);

    const currentSignal = ref({
      symbol: '',
      name: '',
      lastPrice: 0,
      change: 0,
      availableShares: 0,
      recommendation: 'BUY' // 修复：添加缺失的属性
    });

    const availableCash = ref(100000);

    const form = reactive({
      direction: 'BUY',
      priceType: 'LIMIT',
      price: 0,
      quantity: 100,
      account: ''
    });

    const rules = {
      price: [
        {required: true, message: '请输入委托价格', trigger: 'blur'},
        {type: 'number', min: 0.01, message: '价格必须大于0', trigger: 'blur'}
      ],
      quantity: [
        {required: true, message: '请输入委托数量', trigger: 'blur'},
        {type: 'number', min: 100, message: '最小交易100股', trigger: 'blur'}
      ],
      account: [
        {required: true, message: '请选择交易账户', trigger: 'change'}
      ]
    };

    watch(() => props.signal, (newVal) => {
      if (newVal && newVal.symbol) {
        currentSignal.value = {
          symbol: newVal.symbol || '',
          name: newVal.name || '',
          lastPrice: newVal.lastPrice || 0,
          change: newVal.change || 0,
          availableShares: newVal.availableShares || 0,
          recommendation: newVal.recommendation || 'BUY' // 确保赋值
        };
        form.price = newVal.lastPrice;
        form.direction = newVal.recommendation === 'BUY' ? 'BUY' : 'SELL';
        visible.value = true;
      }
    });

    const resetForm = () => {
      if (tradeForm.value) {
        tradeForm.value.resetFields();
      }
      form.price = 0;
      form.quantity = 100;
      currentSignal.value = {
        symbol: '',
        name: '',
        lastPrice: 0,
        change: 0,
        availableShares: 0,
        recommendation: 'BUY' // 重置时也包含属性
      };
    };

    const submitForm = () => {
      tradeForm.value.validate((valid) => {
        if (valid) {
          submitting.value = true;

          // 模拟API请求
          setTimeout(() => {
            emit('submit', {
              ...form,
              symbol: currentSignal.value.symbol,
              name: currentSignal.value.name
            });
            submitting.value = false;
            visible.value = false;
          }, 800);
        }
      });
    };

    return {
      visible,
      currentSignal,
      availableCash,
      form,
      rules,
      tradeForm,
      submitting,
      resetForm,
      submitForm
    };
  }
}
</script>

<style scoped>
.price-tips, .quantity-tips {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.total-amount {
  font-size: 18px;
  font-weight: bold;
  color: #f56c6c;
}

.up {
  color: #f56c6c;
}

.down {
  color: #5cb87a;
}

.dialog-footer {
  text-align: right;
}
</style>
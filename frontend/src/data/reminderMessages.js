/**
 * Personality-driven reminder messages used by the periodic reminder system.
 *
 * Structure:
 *   reminderMessages[period][slot][personality] = string
 *   reminderMessages.random = string[]
 *
 * `period` ∈ {morning, forenoon, noon, afternoon, evening, midnight, periodic, special}
 * `personality` ∈ {gentle, active, tsundere}
 *
 * Lifted verbatim from the original App.vue:393–548 (no behavior changes).
 */

export const reminderMessages = {
  morning: {
    wakeup: {
      gentle: '早安呀～新的一天开始啦，伸个懒腰起床吧，记得喝一杯温水唤醒身体哦',
      active: '叮！你的专属叫醒服务已上线！快起床快起床，太阳都晒屁股啦～',
      tsundere: '喂，还睡呢？再不起床上班/上学就要迟到了，我可不会等你哦',
    },
    breakfast: {
      gentle: '早餐是一天中最重要的一餐，再忙也要记得吃点东西呀',
      active: '干饭时间到！早餐吃什么？包子油条还是牛奶面包？快告诉我！',
      tsundere: '哼，我才不是关心你呢，只是不吃早餐会胃疼，到时候别赖我没提醒你',
    },
    出门: {
      gentle: '出门前记得检查一下钥匙、手机和钱包，还有今天的天气哦',
      active: '出发出发！今天也要元气满满地度过呀！',
      tsundere: '喂，东西都带齐了吗？丢三落四的，我可不会帮你捡东西',
    },
  },
  forenoon: {
    work: {
      gentle: '开始工作/学习啦，先整理一下今天的任务清单吧',
      active: '冲鸭！今天也要努力搬砖/好好学习呀！',
      tsundere: '别发呆了，赶紧干活，不然晚上又要加班了',
    },
    snack: {
      gentle: '工作/学习了一个多小时了，休息一下吧，吃点小零食补充能量',
      active: '摸鱼时间到！快起来活动活动，顺便吃点好吃的～',
      tsundere: '喂，都坐了一上午了，再不动弹就要长肉肉了',
    },
  },
  noon: {
    lunch: {
      gentle: '中午好呀，该吃午饭了，记得荤素搭配，营养均衡哦',
      active: '干饭人干饭魂！干饭时间到！冲啊！',
      tsundere: '终于到吃饭时间了，再不吃我都要饿扁了',
    },
    nap: {
      gentle: '吃完午饭休息一会儿吧，小憩20分钟下午会更有精神哦',
      active: '午睡时间到！闭上眼睛休息一下吧，我会帮你看着时间的',
      tsundere: '赶紧睡会儿，不然下午打瞌睡被老板/老师抓到我可不管',
    },
  },
  afternoon: {
    work: {
      gentle: '午休结束啦，洗把脸清醒一下，继续下午的工作/学习吧',
      active: '睡醒啦睡醒啦！下午也要加油哦！',
      tsundere: '别睡了别睡了，再睡一天就过去了',
    },
    tea: {
      gentle: '下午有点困了吧？喝杯咖啡或者茶，再吃点小点心吧',
      active: '下午茶时间到！让我们一起补充能量，再战一下午！',
      tsundere: '喂，都快睡着了吧？起来喝点东西提提神',
    },
    offWork: {
      gentle: '今天辛苦啦，收拾一下东西准备回家吧',
      active: '解放啦解放啦！终于可以回家啦！',
      tsundere: '终于下班了，再不走我就自己先溜了',
    },
  },
  evening: {
    dinner: {
      gentle: '晚上好呀，该吃晚饭了，不要吃太油腻的东西哦',
      active: '晚餐时间到！今天晚上吃什么好吃的呀？',
      tsundere: '赶紧吃饭，不然一会儿又要吃夜宵了',
    },
    exercise: {
      gentle: '吃完饭休息一会儿，起来运动一下吧，散步或者做瑜伽都可以哦',
      active: '生命在于运动！快起来动一动，甩掉一天的疲惫～',
      tsundere: '喂，吃完就躺着，你是猪吗？赶紧起来运动',
    },
    bedtime: {
      gentle: '时间不早了，准备洗漱睡觉吧，放下手机，让眼睛休息一下',
      active: '洗漱时间到！刷刷牙洗洗脸，舒舒服服睡个好觉～',
      tsundere: '别玩手机了，赶紧去洗漱，不然明天又起不来了',
    },
  },
  midnight: {
    stayUp: {
      gentle: '已经十一点了，该睡觉了，熬夜对身体不好哦',
      active: '很晚啦很晚啦！快睡觉快睡觉，不然会有黑眼圈的！',
      tsundere: '喂，还不睡？想秃头吗？赶紧给我睡觉去',
    },
    forcedSleep: {
      gentle: '已经十二点了，真的该睡觉了，明天还要早起呢',
      active: '晚安晚安！再不睡觉我就要生气了哦！',
      tsundere: '我警告你，现在立刻马上睡觉，不然我就不理你了',
    },
    lateWork: {
      gentle: '都一点了，别再工作/学习了，身体最重要，先睡觉吧',
      active: '救命啊！你怎么还不睡觉？再这样下去身体会垮掉的！',
      tsundere: '你是铁打的吗？都一点了还不睡觉，我都困死了',
    },
  },
  periodic: {
    drinkWater: {
      gentle: '该喝水啦，多喝水对身体好哦',
      active: '咕嘟咕嘟～喝水时间到！快喝一大杯水！',
      tsundere: '喂，喝水了，别等渴了才喝',
    },
    move: {
      gentle: '坐了一个小时了，起来活动一下吧，伸伸胳膊踢踢腿',
      active: '起来动一动！扭扭脖子扭扭腰，预防颈椎病～',
      tsundere: '再坐下去就要变成石头了，赶紧起来活动',
    },
    eyeCare: {
      gentle: '看屏幕看了两个小时了，看看远处，让眼睛休息一下吧',
      active: '护眼时间到！闭上眼睛休息5分钟，或者看看窗外的绿色植物～',
      tsundere: '眼睛不要了吗？赶紧看看远处，别一直盯着屏幕',
    },
    longSit: {
      gentle: '你已经连续坐了两个小时了，起来走一走，倒杯水或者上个厕所吧',
      active: '久坐伤身！快起来溜达溜达，不然屁股会变大的！',
      tsundere: '你是粘在椅子上了吗？赶紧起来走两步',
    },
  },
  special: {
    phoneTime: {
      gentle: '你已经看了一个小时手机了，放下手机休息一下吧',
      active: '手机有什么好看的？看看我呀！快放下手机！',
      tsundere: '再看手机眼睛就要瞎了，赶紧放下',
    },
    forgetMeal: {
      gentle: '你是不是忘记吃饭了？再忙也要按时吃饭呀',
      active: '干饭时间都过了！你怎么还不吃饭？快饿死了吗？',
      tsundere: '连饭都忘记吃，你还能记得什么？赶紧去吃饭',
    },
    yawn: {
      gentle: '困了吗？如果太累了就休息一会儿吧',
      active: '哈哈，你打哈欠了！是不是困啦？',
      tsundere: '困了就去睡，别硬撑着',
    },
    completeTask: {
      gentle: '太棒了！你完成了今天的任务，奖励自己休息一下吧',
      active: '哇塞！你太厉害了！任务完成！',
      tsundere: '哼，终于完成了，还不算太笨',
    },
    birthday: {
      gentle: '今天是你的生日呀，祝你生日快乐！',
      active: '生日快乐！今天要开心哦！',
      tsundere: '喂，今天是你的生日，我可没忘哦',
    },
    holiday: {
      gentle: '今天是{holiday}呀，祝你节日快乐！',
      active: '{holiday}快乐！今天要开心哦！',
      tsundere: '喂，今天是{holiday}，我可没忘哦',
    },
  },
  random: [
    '今天也要开心呀！',
    '你在做什么呢？我一直在陪着你哦',
    '累了就休息一下，不要太勉强自己',
    '你今天真好看/真厉害！',
    '有什么不开心的事情可以跟我说呀',
    '我会一直陪着你的',
  ],
}

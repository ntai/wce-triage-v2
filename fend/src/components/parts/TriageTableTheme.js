function value_to_color(value) {
  return value > 100 ? '#FF1f1f'
    : value === 100 ? '#00ef0f'
      : value > 0 ? '#5f8fff'
        : '#dadada';
}


function value_to_bgcolor(value) {
  return value > 100 ? '#FFEEEE'
    : value === 100 ? '#EEFFEE'
      : value > 0 ? '#EEEEFF'
        : '#EEEEEE';
}


export { value_to_color, value_to_bgcolor }

import bisect
import gevent


def quantize_without_going_over(value, quant, with_index=False):
    """Quantizes a value to the closest value in a list of quantized values,
        where the closest value must be equal or higher than the provided value.
    Args:
        value (float): Value to be quantized
        quant (list[float]): Quantized value options.
    Returns:
        float: Quantized input value.
    """
    mids = [(quant[i] + quant[i + 1]) / 2.0
            for i in range(len(quant) - 1)]
    ind = bisect.bisect_right(mids, value)
    if quant[ind] < value and ind < len(quant) - 1:
        ind += 1
    if with_index:
        return ind, quant[ind]
    else:
        return quant[ind]
